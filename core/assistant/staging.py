"""Staged-change constructor — the single entry point every emitter uses.

Staged-changes design §2 (docs/superpowers/specs/
2026-07-05-staged-changes-routines-design.md): routines/skills/tools that run
with ``context={'staged': True}`` record an OpsProposal here instead of
writing. ``core.safety`` class-blocklist checks run at STAGING time, so a
forbidden class (``pricing_change`` etc.) can't even be proposed.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from core.assistant.models import OpsProposal
from core.safety import SafetyViolation, is_class_allowed

DEFAULT_TTL = timedelta(days=7)  # stale proposals auto-expire — data drifts


def stage_proposal(
    *,
    source: str,
    kind: str,
    title: str,
    summary: str,
    changes: list[dict],
    agent_run=None,
    target=None,
) -> OpsProposal:
    """Create a ``status='proposed'`` OpsProposal (expires in 7 days).

    ``changes`` is ``[{object: '<app_label>.<model>:<pk>', field, old, new}, …]``.
    Raises SafetyViolation if ``kind`` is in core.safety.CLASS_BLOCKLIST.
    """
    if not is_class_allowed(kind):
        raise SafetyViolation([f'kind {kind!r} is blocklisted (core.safety.CLASS_BLOCKLIST)'])
    proposal = OpsProposal(
        source=str(source)[:80],
        kind=str(kind)[:40],
        title=str(title)[:200],
        summary=str(summary or ''),
        changes=list(changes or []),
        agent_run=agent_run,
        status='proposed',
        expires_at=timezone.now() + DEFAULT_TTL,
    )
    if target is not None:
        proposal.target = target
    proposal.save()
    return proposal
