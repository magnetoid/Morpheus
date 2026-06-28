"""Celery tasks for the Morpheus Brain surface.

The long-form advisory briefing is generated here (in the plugin that owns the
BrainBriefing model) rather than in core/brain — core must not import plugin
models. Scheduled on a 6-hour beat by the plugin's ready(); also callable from
the "Regenerate briefing" action.
"""

from __future__ import annotations

from celery import shared_task


@shared_task(name='morpheus_brain.generate_briefing')
def generate_briefing_task() -> dict:
    """Re-run the AI advisory briefing and persist it. No-op (status dict) when
    no AI provider is configured."""
    from plugins.installed.morpheus_brain.services import generate_briefing

    result = generate_briefing()
    # Return a JSON-safe status (not the model instance) for the task result.
    return {
        'configured': result.get('configured'),
        'error': result.get('error'),
        'generated': bool(result.get('briefing')),
    }
