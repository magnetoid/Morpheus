"""Background tasks for the core Assistant.

Beat-scheduled jobs are registered by `morph/celery.py` via the
plugin `_register_beat_schedule()` pattern — this module only
defines the task callables.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger('morpheus.assistant')


@shared_task(bind=True, time_limit=600, soft_time_limit=540)
def daily_briefing(self) -> dict:
    """Generate Linda's morning briefing (see core/assistant/briefing.py).
    No-ops when the feature is off, no provider is configured, or today's
    briefing already exists."""
    from core.assistant.briefing import run_daily_briefing

    return run_daily_briefing()


@shared_task(bind=True, time_limit=600, soft_time_limit=540)
def tool_gap_flywheel(self) -> dict:
    """Weekly: draft CodeProposals for tool gaps the reflection loop has
    seen at least twice (see core/assistant/flywheel.py). Propose-only."""
    from core.assistant.flywheel import run_tool_gap_flywheel

    return run_tool_gap_flywheel()


@shared_task(bind=True, time_limit=300, soft_time_limit=240)
def decay_assistant_memories(self) -> dict:
    """Forget memories whose decayed relevance has fallen near zero.

    Threshold: 0.05 — equivalent to either:
      - a user-told fact older than ~260 days, OR
      - an inferred fact older than ~150 days.

    Returns ``{checked, removed}`` for observability.
    """
    try:
        from core.assistant.models import LindaMemory
    except Exception:  # noqa: BLE001 — table not yet migrated
        return {'checked': 0, 'removed': 0, 'error': 'model unavailable'}

    threshold = 0.05
    removed_ids = []
    checked = 0
    for row in LindaMemory.objects.all().iterator(chunk_size=500):
        checked += 1
        if row.relevance_score() < threshold:
            removed_ids.append(row.id)
    if removed_ids:
        LindaMemory.objects.filter(id__in=removed_ids).delete()
    logger.info('decay_assistant_memories: checked=%d removed=%d', checked, len(removed_ids))
    return {'checked': checked, 'removed': len(removed_ids)}
