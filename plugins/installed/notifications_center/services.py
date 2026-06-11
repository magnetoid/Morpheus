"""Public API: `notify(user, kind, title, ...)`.

Plugins call this instead of writing Notification rows directly so the
fan-in stays centralised. Future extensions (per-user preferences,
digest emails, push notifications) plug in here without per-call-site
changes.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from django.contrib.auth import get_user_model

from plugins.installed.notifications_center.models import Notification

logger = logging.getLogger('morpheus.notifications_center')


def notify(
    *, user, kind: str, title: str, body: str = '', action_url: str = '', icon: str = 'bell'
) -> Notification | None:
    """Create a notification for a single staff user.

    Returns the row on success, ``None`` on bad input. Never raises —
    notifications are best-effort; a missing user or DB error logs and
    moves on.
    """
    if user is None or not getattr(user, 'pk', None):
        return None
    try:
        return Notification.objects.create(
            user=user,
            kind=kind[:80],
            title=title[:200],
            body=body or '',
            action_url=action_url[:500] if action_url else '',
            icon=icon[:40] if icon else 'bell',
        )
    except Exception as e:  # noqa: BLE001
        logger.warning('notify failed for user=%s kind=%s: %s', user.pk, kind, e, exc_info=True)
        return None


def notify_all_staff(
    *, kind: str, title: str, body: str = '', action_url: str = '', icon: str = 'bell'
) -> int:
    """Fan out to every staff user. Returns the count actually written.

    Use this for events that don't have a single owner (e.g. "low stock
    on SKU XYZ", "agent run failed"). Per-user preferences (which kinds
    they want) are checked here once they exist; for now everyone gets
    everything.
    """
    User = get_user_model()
    staff = User.objects.filter(is_staff=True, is_active=True)
    written = 0
    for u in staff:
        if (
            notify(user=u, kind=kind, title=title, body=body, action_url=action_url, icon=icon)
            is not None
        ):
            written += 1
    return written


def unread_count_for(user) -> int:
    if user is None or not getattr(user, 'pk', None):
        return 0
    try:
        return Notification.objects.filter(user=user, read_at__isnull=True).count()
    except Exception as e:  # noqa: BLE001
        logger.debug('unread count failed: %s', e)
        return 0


def latest_for(user, *, limit: int = 10) -> Iterable[Notification]:
    """Latest N notifications for a user, newest first. Used by the
    topbar bell dropdown."""
    if user is None or not getattr(user, 'pk', None):
        return []
    try:
        return list(
            Notification.objects.filter(user=user).order_by('-created_at')[
                : max(1, min(int(limit), 50))
            ]
        )
    except Exception as e:  # noqa: BLE001
        logger.debug('latest_for failed: %s', e)
        return []
