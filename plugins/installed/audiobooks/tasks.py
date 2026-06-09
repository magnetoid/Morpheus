"""audiobooks — Celery tasks."""

# ruff: noqa: PLC0415
from __future__ import annotations

import logging

from morph.celery import app

logger = logging.getLogger('morpheus.audiobooks')


@app.task(name='audiobooks.generate')
def generate_audiobook(audiobook_id: str) -> dict:
    """Generate narration for an Audiobook (ElevenLabs). Enqueued by the
    dashboard 'Generate' button; safe to retry."""
    from plugins.installed.audiobooks.models import Audiobook
    from plugins.installed.audiobooks.services import generate

    audiobook = Audiobook.objects.filter(id=audiobook_id).select_related('variant').first()
    if audiobook is None:
        return {'ok': False, 'reason': 'audiobook not found'}
    return generate(audiobook)
