"""Morpheus Brain — continuous analysis task.

Refreshes the cached AI analysis on a schedule so the console always shows a
recent read of the system. Scheduled by the morpheus_brain surface plugin's
``ready()`` (Celery beat). No-op cost when no AI provider is configured.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger('morpheus.brain')


@shared_task(name='core.brain.refresh_analysis')
def refresh_analysis() -> dict:
    """Re-run the Brain's AI analysis and cache it."""
    from core.brain.analyst import get_analysis

    result = get_analysis(force=True)
    logger.info(
        'brain: analysis refreshed (configured=%s, %d recommendations)',
        result.get('configured'),
        len(result.get('recommendations') or []),
    )
    return {
        'configured': result.get('configured'),
        'count': len(result.get('recommendations') or []),
    }
