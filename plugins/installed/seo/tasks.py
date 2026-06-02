"""SEO background tasks."""

# ruff: noqa: PLC0415 — Django imports are lazy (task body runs in the worker).
from __future__ import annotations

import io

from morph.celery import app

_STATUS_KEY = 'seo:image_optimize:status'


@app.task(name='seo.optimize_images', ignore_result=True)
def optimize_images_task(widths: str = '', avif: bool = False) -> None:
    """Run the ``optimize_images`` batch warmer in the background and stash a
    one-line summary in the cache for the SEO settings page to display.

    Non-blocking by design — the dashboard enqueues this so warming the whole
    back-catalogue never holds a request open.
    """
    from django.core.cache import cache
    from django.core.management import call_command
    from django.utils import timezone

    cache.set(_STATUS_KEY, {'state': 'running', 'when': timezone.now().isoformat()}, 7200)
    buf = io.StringIO()
    try:
        args: list[str] = []
        if widths:
            args += ['--widths', widths]
        if avif:
            args += ['--avif']
        call_command('optimize_images', *args, stdout=buf)
        lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
        cache.set(
            _STATUS_KEY,
            {
                'state': 'done',
                'summary': lines[-1] if lines else 'done',
                'when': timezone.now().isoformat(),
            },
            86400,
        )
    except Exception as e:  # noqa: BLE001 — record the failure for the dashboard, then re-raise
        cache.set(
            _STATUS_KEY,
            {'state': 'failed', 'summary': str(e)[:300], 'when': timezone.now().isoformat()},
            86400,
        )
        raise


def last_image_optimize_status() -> dict | None:
    """Cached status dict for the settings page (``None`` until first run)."""
    from django.core.cache import cache

    return cache.get(_STATUS_KEY)
