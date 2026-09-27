"""SEO background tasks."""

# ruff: noqa: PLC0415 — Django imports are lazy (task body runs in the worker).
from __future__ import annotations

import io
import logging

from morph.celery import app

logger = logging.getLogger('morpheus.seo.tasks')

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


# Its own budget: the global 4/5-minute limits cannot hold a full crawl
# (dotbooks' sitemap is ~3,700 URLs), so the worker was SIGKILLed mid-audit
# every night. On the soft limit the audit stops and stores what it checked.
@app.task(name='seo.site_audit', ignore_result=True, soft_time_limit=1800, time_limit=1920)
def site_audit_task(limit: int = 0) -> None:
    """Nightly site-wide SEO crawl — see `services/site_audit.py`.

    Runs off-request because it renders every URL in the sitemap. Failures are
    swallowed: a missed night shows the previous report (the cache outlives a
    daily run by two hours) rather than an empty page.
    """
    from plugins.installed.seo.services.site_audit import run_and_store

    try:
        report = run_and_store(limit=limit or None)
        logger.info(
            'seo.site_audit: %s pages, score %s, %s finding(s)',
            report['pages_checked'],
            report['score'],
            len(report['findings']),
        )
    except Exception:  # noqa: BLE001
        logger.warning('seo.site_audit failed', exc_info=True)
