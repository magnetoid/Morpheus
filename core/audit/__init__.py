"""Security-grade audit logging.

    from core.audit import record

    record(
        event_type='rbac.role_granted',
        actor=request.user,
        target='user/abc-123',
        metadata={'role': 'admin', 'channel': 'us'},
    )

The intent is a single tamper-evident trail of "who changed what,
when" — distinct from `AgentStep` (per-step LLM trace) and from
ordinary application logs (transient operational noise). Reads cheap;
writes are deliberately small.
"""

from __future__ import annotations

from core.audit.services import record

__all__ = ['record']
