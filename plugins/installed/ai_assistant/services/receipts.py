"""
Agent receipts: signed audit records that prove which agent did what, when,
on whose behalf, and at what cost.

A receipt is a JSON envelope:

    {
        "intent_id": "...",
        "agent_id": "...",
        "kind": "checkout",
        "state": "completed",
        "result": {...},
        "actual_cost": {"amount": "12.50", "currency": "USD"},
        "issued_at": "2026-04-25T17:30:00Z"
    }

It is signed with the agent's `signing_secret` (HMAC-SHA256 over the canonical
JSON encoding) and stored on the AgentIntent. Any downstream consumer
(merchant audit dashboard, fraud worker, customer wallet) can verify.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from django.utils import timezone as dj_timezone


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    """Stable JSON serialization suitable for HMAC signing."""

    def _default(o: Any) -> Any:
        if isinstance(o, Decimal):
            return str(o)
        if isinstance(o, datetime):
            return o.astimezone(UTC).isoformat()
        raise TypeError(f'Cannot serialize {type(o).__name__}')

    return json.dumps(
        payload,
        sort_keys=True,
        separators=(',', ':'),
        default=_default,
    ).encode('utf-8')


def build_receipt_payload(intent) -> dict[str, Any]:
    """Build the deterministic receipt envelope for an AgentIntent."""
    actual_cost = None
    if intent.actual_cost is not None:
        actual_cost = {
            'amount': str(intent.actual_cost.amount),
            'currency': str(intent.actual_cost.currency),
        }
    return {
        'intent_id': str(intent.id),
        'agent_id': intent.agent.agent_id,
        'kind': intent.kind,
        'state': intent.state,
        'result': intent.result or {},
        'actual_cost': actual_cost,
        'customer_id': str(intent.customer_id) if intent.customer_id else None,
        'channel_id': str(intent.channel_id) if intent.channel_id else None,
        'correlation_id': intent.correlation_id or '',
        'issued_at': dj_timezone.now().astimezone(UTC).isoformat(),
    }


def sign_receipt(intent, secret: str) -> tuple[dict[str, Any], str]:
    """Build and sign a receipt for `intent`. Returns (payload, signature)."""
    payload = build_receipt_payload(intent)
    body = _canonical_json(payload)
    signature = hmac.new(
        secret.encode('utf-8'),
        body,
        hashlib.sha256,
    ).hexdigest()
    return payload, signature


def verify_receipt(payload: Mapping[str, Any], signature: str, secret: str) -> bool:
    """Constant-time verification of an agent receipt."""
    body = _canonical_json(payload)
    expected = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or '')
