"""digital_products plugin — Celery tasks."""
from __future__ import annotations

import logging

from morph.celery import app

logger = logging.getLogger('morpheus.digital_products')


@app.task(name='digital_products.cleanup_expired_tokens')
def cleanup_expired_tokens(grace_days: int = 7) -> int:
    """Delete download tokens that expired more than ``grace_days`` ago.

    We keep recently-expired rows around so the customer still sees a
    polite "this link expired" instead of a 404 if they click an old
    email. Anything older than the grace window is hard-deleted.

    Returns the number of rows deleted. Driven by celery beat from the
    digital_products plugin.ready().
    """
    from datetime import timedelta

    from django.utils import timezone

    try:
        from plugins.installed.digital_products.models import DownloadToken
    except Exception:  # noqa: BLE001 — plugin not migrated yet
        return 0
    cutoff = timezone.now() - timedelta(days=max(0, grace_days))
    deleted, _ = DownloadToken.objects.filter(expires_at__lt=cutoff).delete()
    if deleted:
        logger.info('digital_products: cleaned %d expired token(s)', deleted)
    return deleted
