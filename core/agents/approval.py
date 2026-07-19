"""Approval seam for the agent kernel — fail-closed by default.

The kernel (`core/agents`) is deliberately Django-free, so it cannot look up
approval records itself. A Django-land app (`agent_core`) registers a resolver
here in its ``ready()``; until one is registered, the seam **denies** every
approval-required tool (fail-closed). Mirrors ``provider_config_registry``.

Contract: a denial does NOT mean "rejected" — it means "no approval on record".
The runtime turns a registry denial into a paused run + a pending approval
request (``STEP_APPROVAL_REQUIRED``), never a silent execution.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable

# resolver(tool_name, args, context) -> bool  (True = an approval is on record)
_Resolver = Callable[[str, dict, dict], bool]


def args_fingerprint(tool_name: str, args: dict | None) -> str:
    """Stable fingerprint of one tool invocation (name + canonical args), so an
    approval binds to exactly the call it was granted for — an agent can't get a
    grant for a benign call approved and then execute a different one."""
    blob = json.dumps({'tool': tool_name, 'args': args or {}}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


class _ApprovalRegistry:
    def __init__(self) -> None:
        self._resolver: _Resolver | None = None

    def register(self, resolver: _Resolver) -> None:
        """Install the DB-backed resolver (idempotent — last wins)."""
        self._resolver = resolver

    def reset(self) -> None:
        """Drop the resolver (tests / plugin disable) → back to fail-closed."""
        self._resolver = None

    def check(self, tool_name: str, args: dict, context: dict) -> bool:
        """True only when a resolver affirmatively confirms an approval is on
        record. No resolver, or any resolver error, DENIES — fail-closed."""
        if self._resolver is None:
            return False
        try:
            return bool(self._resolver(tool_name, args or {}, context or {}))
        except Exception:  # noqa: BLE001 — a broken resolver must deny, never allow
            return False


approval_registry = _ApprovalRegistry()
