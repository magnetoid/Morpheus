"""Synchronous + asynchronous Morpheus agent client.

The SDK keeps a tiny GraphQL surface (no codegen, no schema bundling) so it
works against any current or future server schema. Each method maps 1-to-1 to
a documented GraphQL field on the platform.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from morph_sdk.errors import (
    AgentBudgetError,
    MorphError,
    PermissionDeniedError,
    TransportError,
)
from morph_sdk.receipts import AgentReceipt

_GRAPHQL_PATH = '/graphql/agent/'


@dataclass
class _GraphQLResponse:
    data: Any
    errors: list[dict[str, Any]] | None


def _raise_for_errors(resp: _GraphQLResponse) -> None:
    if not resp.errors:
        return
    err = resp.errors[0]
    code = (err.get('extensions') or {}).get('code', '')
    message = err.get('message', 'GraphQL error')
    if code == 'PERMISSION_DENIED':
        raise PermissionDeniedError(message)
    if 'budget' in message.lower():
        raise AgentBudgetError(message)
    raise MorphError(message)


class _GraphQL:
    def __init__(self, base_url: str, agent_token: str, timeout: float):
        self._url = base_url.rstrip('/') + _GRAPHQL_PATH
        self._headers = {
            'Authorization': f'Bearer {agent_token}',
            'Content-Type': 'application/json',
            'X-Agent-Token': agent_token,
        }
        self._timeout = timeout

    def execute(self, query: str, variables: dict[str, Any] | None = None) -> _GraphQLResponse:
        try:
            resp = httpx.post(
                self._url,
                headers=self._headers,
                content=json.dumps({'query': query, 'variables': variables or {}}),
                timeout=self._timeout,
            )
        except httpx.HTTPError as e:
            raise TransportError(f'HTTP error: {e}') from e
        if resp.status_code == 401:
            raise PermissionDeniedError('Invalid or missing agent token')
        if resp.status_code >= 500:
            raise TransportError(f'Server error {resp.status_code}: {resp.text[:200]}')
        body = resp.json()
        return _GraphQLResponse(data=body.get('data'), errors=body.get('errors'))


class MorphAgentClient:
    """High-level Morpheus client for AI agents (sync)."""

    def __init__(
        self,
        base_url: str,
        agent_token: str,
        signing_secret: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._gql = _GraphQL(base_url, agent_token, timeout)
        self._signing_secret = signing_secret or ''

    # ── Catalog ───────────────────────────────────────────────────────────────

    def search_products(self, query: str, first: int = 8) -> list[dict[str, Any]]:
        gql = """
        query Search($q: String!, $n: Int!) {
            semanticSearch(query: $q, first: $n) {
                products { id name slug
                    agentMetadata {
                        sku currency priceAmount inStock
                        urlPath isDigital requiresShipping
                    }
                }
                explanation usedEmbedding
            }
        }
        """
        resp = self._gql.execute(gql, {'q': query, 'n': first})
        _raise_for_errors(resp)
        return list((resp.data or {}).get('semanticSearch', {}).get('products', []))

    # ── Intents ───────────────────────────────────────────────────────────────

    def propose_intent(
        self,
        *,
        kind: str,
        summary: str = '',
        payload: dict[str, Any] | None = None,
        estimated_amount: float | None = None,
        estimated_currency: str = 'USD',
        correlation_id: str = '',
        expires_in_seconds: int = 600,
    ) -> dict[str, Any]:
        gql = """
        mutation Propose($input: ProposeIntentInput!) {
            proposeAgentIntent(input: $input) {
                id kind state summary receiptSignature
            }
        }
        """
        variables = {
            'input': {
                'kind': kind,
                'summary': summary,
                'payloadJson': json.dumps(payload) if payload is not None else None,
                'estimatedAmount': estimated_amount,
                'estimatedCurrency': estimated_currency,
                'correlationId': correlation_id,
                'expiresInSeconds': expires_in_seconds,
            }
        }
        resp = self._gql.execute(gql, variables)
        _raise_for_errors(resp)
        return (resp.data or {}).get('proposeAgentIntent') or {}

    def list_my_intents(self, *, first: int = 25, state: str | None = None) -> list[dict[str, Any]]:
        gql = """
        query MyIntents($n: Int!, $state: String) {
            myAgentIntents(first: $n, state: $state) {
                id kind state summary correlationId receiptSignature createdAt
            }
        }
        """
        resp = self._gql.execute(gql, {'n': first, 'state': state})
        _raise_for_errors(resp)
        return list((resp.data or {}).get('myAgentIntents') or [])

    # ── Receipts ──────────────────────────────────────────────────────────────

    def receipt_for(self, intent: dict[str, Any]) -> AgentReceipt | None:
        """Construct an AgentReceipt from a list_my_intents row + the SDK's signing secret.

        The full receipt payload is currently rebuilt client-side to match
        the platform's canonical encoding. A future SDK release will fetch
        the full payload directly.
        """
        if not intent.get('receiptSignature'):
            return None
        # The platform signs the full receipt; this client-side stub mirrors
        # the schema in `services/receipts.py` for the most common fields.
        payload = {
            'intent_id': intent.get('id', ''),
            'kind': intent.get('kind', ''),
            'state': intent.get('state', ''),
            'correlation_id': intent.get('correlationId', ''),
        }
        return AgentReceipt(
            payload=payload,
            signature=intent['receiptSignature'],
            secret=self._signing_secret,
        )
