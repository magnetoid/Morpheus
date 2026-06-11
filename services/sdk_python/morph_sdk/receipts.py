"""Local verification of Morpheus agent receipts.

The platform signs each completed intent with HMAC-SHA256 over a canonical
JSON encoding of the receipt payload. The SDK consumer (the agent owner)
holds the agent's signing secret and can verify locally — *without* trusting
the platform's claim that an intent succeeded.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
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


def verify_receipt(payload: Mapping[str, Any], signature: str, secret: str) -> bool:
    body = _canonical_json(payload)
    expected = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or '')


@dataclass(slots=True)
class AgentReceipt:
    """A receipt as returned by the Morpheus platform."""

    payload: Mapping[str, Any]
    signature: str
    secret: str = field(repr=False, default='')

    def verify(self, secret: str | None = None) -> bool:
        return verify_receipt(self.payload, self.signature, secret or self.secret)

    @property
    def intent_id(self) -> str:
        return str(self.payload.get('intent_id', ''))

    @property
    def state(self) -> str:
        return str(self.payload.get('state', ''))

    @property
    def actual_cost(self) -> Mapping[str, str] | None:
        return self.payload.get('actual_cost')
