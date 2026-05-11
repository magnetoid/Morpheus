"""Audit recorder — `record(...)` is the only public surface.

Also exposes ``record_ai_decision(...)`` for the EU AI Act / GDPR
provenance trail: every customer-facing personalisation, dynamic-pricing,
or agent tool call should funnel through it so a merchant can later
export the full decision history for a customer or a model.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from core.utils.safe_db import safe_db

logger = logging.getLogger('morpheus.audit')


@safe_db(default=None, log_level=logging.WARNING)
def record(
    *,
    event_type: str,
    actor: Any = None,
    target: str = '',
    metadata: Optional[dict] = None,
    severity: str = 'info',
    ip_address: Optional[str] = None,
    request_id: str = '',
) -> Any:
    """Persist one audit row. Never raises (DB errors are swallowed + logged)."""
    from core.audit.models import AuditEvent

    actor_obj = actor if (actor is not None and getattr(actor, 'is_authenticated', False)) else None
    actor_label = ''
    if actor_obj is not None:
        actor_label = getattr(actor_obj, 'email', '') or getattr(actor_obj, 'username', '') or str(actor_obj.pk)
    elif actor is not None:
        actor_label = str(actor)[:200]

    return AuditEvent.objects.create(
        event_type=event_type[:120],
        severity=severity if severity in dict(AuditEvent.SEVERITY_CHOICES) else AuditEvent.SEVERITY_INFO,
        actor=actor_obj,
        actor_label=actor_label[:200],
        target=str(target)[:200] if target else '',
        metadata=metadata or {},
        ip_address=ip_address,
        request_id=request_id[:64] if request_id else '',
    )


@safe_db(default=None, log_level=logging.WARNING)
def record_ai_decision(
    *,
    agent: str,
    tool: str,
    run_id: str = '',
    args: Optional[dict] = None,
    output: Any = None,
    duration_ms: Optional[int] = None,
    model: str = '',
    provider: str = '',
    actor: Any = None,
    target: str = '',
    request_id: str = '',
) -> Any:
    """Persist one ``agents.decision`` audit row with full provenance.

    Captures the *who* (agent), *what* (tool + args + output),
    *how long* (duration), and *which model* (model + provider) so a
    merchant can export the full chain of automated decisions affecting
    a given customer or order. EU AI Act art. 12 + 13 want this.

    Honors ``MORPH_DISABLE_AI_AUDIT=1`` for development — never set
    this in production; the audit trail is the only artefact a
    regulator will ask for.
    """
    import os
    if os.getenv('MORPH_DISABLE_AI_AUDIT') == '1':
        return None
    metadata = {
        'agent': agent[:120],
        'tool': tool[:120],
        'run_id': str(run_id)[:64] if run_id else '',
        'args': args or {},
        'output': output,
        'duration_ms': duration_ms,
        'model': model[:80],
        'provider': provider[:40],
    }
    return record(
        event_type='agents.decision',
        actor=actor,
        target=target,
        metadata=metadata,
        request_id=request_id,
    )
