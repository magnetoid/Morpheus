"""Exception hierarchy used by the Morph SDK."""

from __future__ import annotations


class MorphError(Exception):
    """Base class for SDK errors."""


class PermissionDeniedError(MorphError):
    """Raised when the server returns a PERMISSION_DENIED extension."""


class AgentBudgetError(MorphError):
    """Raised when an intent would exceed the agent's configured budget."""


class TransportError(MorphError):
    """Raised on HTTP-layer failures (timeouts, 5xx, etc)."""
