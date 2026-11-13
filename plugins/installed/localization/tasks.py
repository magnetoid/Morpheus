"""Localization background tasks: AI drafts of translations (`drafting.py`)."""

# ruff: noqa: PLC0415 — Django imports are lazy (task body runs in the worker).
from __future__ import annotations

from morph.celery import app


# Its own budget: one model call per object, up to 50 objects a run.
@app.task(
    name='localization.draft_translations', ignore_result=True, soft_time_limit=900, time_limit=960
)
def draft_translations(kind: str, language: str, object_ids: list[str]) -> dict:
    """Write AI drafts for the objects, for the merchant to review."""
    from plugins.installed.localization.drafting import run_drafts

    return run_drafts(kind, language, object_ids)
