"""Fail-closed approval resolver + pending-request recorder for the agent kernel.

The kernel (`core/agents`) is Django-free and denies every approval-required
tool until this resolver is registered (agent_core `ready()`). The flow:

  1. kernel hits an approval tool with no approval on record → the registry
     `check` returns False → kernel fires ``STEP_APPROVAL_REQUIRED`` →
     ``record_pending`` writes a pending ``AgentApprovalRequest`` and pauses the
     run (``AgentRun.state='awaiting_approval'``). The tool does NOT run.
  2. a human approves the request in the dashboard (``state='approved'``,
     ``decided_at`` set).
  3. the run is re-invoked → ``resolve`` finds the approved, unconsumed,
     unexpired request, atomically consumes it (single-use), returns True → the
     tool runs exactly once.
"""

from __future__ import annotations

import logging
from datetime import timedelta

logger = logging.getLogger('morpheus.agent_core.approvals')

# How long a human approval stays spendable after the decision (audit C1: 5 min).
_TTL_MINUTES = 5


def resolve(tool_name: str, args: dict, context: dict) -> bool:
    """True iff an approved, unconsumed, unexpired request matches this exact
    call (run + tool + args fingerprint). Consumes it atomically on match."""
    from django.utils import timezone

    from core.agents.approval import args_fingerprint
    from plugins.installed.agent_core.models import AgentApprovalRequest

    run = (context or {}).get('agent_run')
    if run is None:
        return False
    fp = args_fingerprint(tool_name, args)
    cutoff = timezone.now() - timedelta(minutes=_TTL_MINUTES)
    req = (
        AgentApprovalRequest.objects.filter(
            run=run,
            tool_name=tool_name,
            args_fingerprint=fp,
            state='approved',
            consumed_at__isnull=True,
            decided_at__gte=cutoff,
        )
        .order_by('-decided_at')
        .first()
    )
    if req is None:
        return False
    # Single-use: only the writer that flips consumed_at gets to run the tool.
    claimed = AgentApprovalRequest.objects.filter(pk=req.pk, consumed_at__isnull=True).update(
        consumed_at=timezone.now()
    )
    return claimed == 1


def record_pending(
    agent=None, tool=None, run_id=None, arguments=None, context=None, **kwargs
) -> None:
    """Record a pending approval request + pause the run. Idempotent: only one
    open pending request per (run, tool, fingerprint)."""
    from core.agents.approval import args_fingerprint
    from plugins.installed.agent_core.models import AgentApprovalRequest, AgentRun

    run = (context or {}).get('agent_run')
    if run is None:
        # No AgentRun in scope (e.g. an ephemeral spawned worker) — nothing to
        # pause or attach the request to. The kernel already denied the tool.
        return
    fp = args_fingerprint(tool, arguments)
    try:
        exists = AgentApprovalRequest.objects.filter(
            run=run, tool_name=tool or '', args_fingerprint=fp, state='pending'
        ).exists()
        if not exists:
            AgentApprovalRequest.objects.create(
                run=run,
                tool_name=tool or '',
                args_fingerprint=fp,
                arguments=arguments or {},
                state='pending',
            )
        # Pause the run so it can be resumed after a human decision. Never
        # reopen an already-terminal run.
        AgentRun.objects.filter(pk=run.pk).exclude(
            state__in=('awaiting_approval', 'failed', 'succeeded', 'cancelled', 'error')
        ).update(state='awaiting_approval')
    except Exception:  # noqa: BLE001 — recording must never crash the agent loop
        logger.warning('record_pending failed for tool %s', tool, exc_info=True)


def register() -> None:
    """Wire the resolver into the kernel seam + subscribe the recorder."""
    from core.agents.approval import approval_registry
    from core.agents.events import AgentEvents
    from morpheus.core import hook_registry

    approval_registry.register(resolve)
    hook_registry.register(AgentEvents.STEP_APPROVAL_REQUIRED, record_pending, priority=50)
