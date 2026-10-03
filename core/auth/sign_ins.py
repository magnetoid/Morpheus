"""Sign-in log: when each customer or admin signed in, from where, on what.

Every sign-in route (emailed code, allauth password, staff two-factor, SSO)
ends in Django's ``login()``, which sends ``user_logged_in``. ``record_sign_in``
is connected to that signal in ``CoreAuthConfig.ready()``, so no route can skip
the log. Entries live in the audit log and are kept for ``KEEP_DAYS``: an IP
address is personal data.
"""

from __future__ import annotations

import ipaddress
import logging
from datetime import timedelta

logger = logging.getLogger('morpheus.core.auth')

SIGN_IN_EVENT = 'auth.sign_in'
KEEP_DAYS = 90

# (marker in the user agent, name); the first match wins. Edge and Opera also
# say "Chrome", and Chrome also says "Safari", so the specific ones come first.
_BROWSERS = (
    ('Edg/', 'Edge'),
    ('OPR/', 'Opera'),
    ('SamsungBrowser/', 'Samsung Internet'),
    ('CriOS/', 'Chrome'),
    ('Chrome/', 'Chrome'),
    ('FxiOS/', 'Firefox'),
    ('Firefox/', 'Firefox'),
    ('Safari/', 'Safari'),
)
# iPhone and iPad say "like Mac OS X", and Android says "Linux".
_SYSTEMS = (
    ('iPhone', 'iPhone'),
    ('iPad', 'iPad'),
    ('Android', 'Android'),
    ('Windows', 'Windows'),
    ('CrOS', 'ChromeOS'),
    ('Macintosh', 'Mac'),
    ('Linux', 'Linux'),
)


def describe_device(user_agent: str) -> str:
    """'Chrome on Mac' from a user-agent string, or 'Unknown device'."""
    ua = user_agent or ''
    browser = next((name for marker, name in _BROWSERS if marker in ua), '')
    system = next((name for marker, name in _SYSTEMS if marker in ua), '')
    if browser and system:
        return f'{browser} on {system}'
    return browser or system or 'Unknown device'


def _client_ip(request) -> str | None:
    """The visitor's address, by the rule ``core/ratelimit.py:_client_id``
    uses: Cloudflare's CF-Connecting-IP (a visitor can't set it), then the
    first X-Forwarded-For entry, then the direct peer. None unless it is an IP.
    """
    meta = getattr(request, 'META', None) or {}
    raw = (
        meta.get('HTTP_CF_CONNECTING_IP', '')
        or meta.get('HTTP_X_FORWARDED_FOR', '').split(',')[0]
        or meta.get('REMOTE_ADDR', '')
    ).strip()
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return None


def record_sign_in(sender, request, user, **kwargs) -> None:
    """``user_logged_in`` receiver: one audit entry per successful sign-in."""
    from core.audit.services import record

    try:
        meta = getattr(request, 'META', None) or {}
        user_agent = (meta.get('HTTP_USER_AGENT') or '')[:300]
        record(
            event_type=SIGN_IN_EVENT,
            actor=user,
            target=f'user/{user.pk}',
            ip_address=_client_ip(request),
            metadata={'device': describe_device(user_agent), 'user_agent': user_agent},
        )
    except Exception:  # noqa: BLE001 — a failed log entry must never block a sign-in
        logger.warning('sign-in log: could not record a sign-in', exc_info=True)


def recent_sign_ins(user, limit: int = 10) -> list[dict]:
    """The person's newest sign-ins, newest first: ``{'at', 'ip', 'device'}``."""
    from core.audit.models import AuditEvent

    rows = AuditEvent.objects.filter(event_type=SIGN_IN_EVENT, actor=user).order_by('-created_at')[
        :limit
    ]
    return [
        {
            'at': row.created_at,
            'ip': row.ip_address,
            'device': (row.metadata or {}).get('device') or 'Unknown device',
        }
        for row in rows
    ]


def prune_sign_ins(keep_days: int = KEEP_DAYS) -> int:
    """Delete sign-in entries older than ``keep_days``; returns how many."""
    from django.utils import timezone

    from core.audit.models import AuditEvent

    cutoff = timezone.now() - timedelta(days=keep_days)
    deleted, _ = AuditEvent.objects.filter(event_type=SIGN_IN_EVENT, created_at__lt=cutoff).delete()
    return deleted
