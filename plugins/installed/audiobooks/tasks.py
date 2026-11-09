"""audiobooks — Celery tasks."""

# ruff: noqa: PLC0415
from __future__ import annotations

import logging

from django.conf import settings

from morph.celery import app

logger = logging.getLogger('morpheus.audiobooks')


@app.task(name='audiobooks.generate')
def generate_audiobook(audiobook_id: str) -> dict:
    """Run one slice of an audiobook's narration job (services.run) and queue the
    next one while the job goes on. Queued by the product card and Linda's
    ``audiobooks.generate``; safe to repeat, since a slice skips saved pieces."""
    from plugins.installed.audiobooks.services import run

    result = run(audiobook_id)
    again = result.get('again')
    # Tests run tasks inline, where a queued slice would run at once, inside this
    # one; they call run() slice by slice instead.
    if again is not None and not getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
        generate_audiobook.apply_async((audiobook_id,), countdown=again)
    return result
