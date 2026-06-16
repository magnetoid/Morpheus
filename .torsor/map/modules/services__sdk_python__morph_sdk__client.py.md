---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# services/sdk_python/morph_sdk/client.py

Symbols in `services/sdk_python/morph_sdk/client.py`.

- L28 `_GraphQLResponse` (class)
- L33 `_raise_for_errors(resp: _GraphQLResponse)` (function)
- L46 `_GraphQL` (class)
- L47 `__init__(self, base_url: str, agent_token: str, timeout: float)` (method)
- L56 `execute(self, query: str, variables: dict[str, Any] | None=None)` (method)
- L74 `MorphAgentClient` (class) — High-level Morpheus client for AI agents (sync).
- L77 `__init__(self, base_url: str, agent_token: str, signing_secret: str | None=None, timeout: float=15.0)` (method)
- L89 `search_products(self, query: str, first: int=8)` (method)
- L109 `propose_intent(self, *, kind: str, summary: str='', payload: dict[str, Any] | None=None, estimated_amount: float | None=None, estimated_currency: str='USD', correlation_id: str='', expires_in_seconds: int=600)` (method)
- L142 `list_my_intents(self, *, first: int=25, state: str | None=None)` (method)
- L156 `receipt_for(self, intent: dict[str, Any])` (method) — Construct an AgentReceipt from a list_my_intents row + the SDK's signing secret.
