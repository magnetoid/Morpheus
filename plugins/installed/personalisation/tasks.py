"""Nightly co-purchase recompute."""

from __future__ import annotations

from celery import shared_task

from plugins.installed.personalisation.services import recompute_copurchases


@shared_task(name='personalisation.recompute_copurchases')
def recompute_copurchases_task(window_days: int = 90, top_k: int = 12) -> dict:
    return recompute_copurchases(window_days=window_days, top_k=top_k)
