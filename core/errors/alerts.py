"""Tell a person when the store breaks.

Errors were captured into ``ErrorEvent`` all along and shown on
/dashboard/errors/ — which nobody opens. Supernatural's product pages returned
500 for ten days in September (hundreds of captures) before anyone looked. This
module turns the log into two emails: a daily digest of the day's server errors,
and an immediate alert when the nightly health check fails (``core.errors.health``).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count, Max
from django.utils import timezone

logger = logging.getLogger('morpheus.errors.alerts')


def alert_recipients() -> list[str]:
    """Who hears about problems: ``ERROR_ALERT_EMAILS`` (comma-separated), else the
    active superusers — the people who run the store — else its public contact
    address (a customer-facing inbox, so only as a last resort)."""
    configured = getattr(settings, 'ERROR_ALERT_EMAILS', '') or ''
    if isinstance(configured, str):
        configured = [e.strip() for e in configured.split(',')]
    emails = [e for e in configured if e and '@' in e]
    if emails:
        return emails
    from django.contrib.auth import get_user_model

    operators = sorted(
        {
            e
            for e in get_user_model()
            .objects.filter(is_superuser=True, is_active=True)
            .values_list('email', flat=True)
            if e
        }
    )
    if operators:
        return operators
    from core.utils.site import store_contact_email

    contact = store_contact_email()
    return [contact] if contact else []


def send_alert(subject: str, body: str) -> bool:
    """Email ``alert_recipients()``. Fail-soft: an alert must never raise."""
    recipients = alert_recipients()
    if not recipients:
        logger.warning('errors.alerts: no recipient for "%s"', subject)
        return False
    try:
        send_mail(subject, body, None, recipients, fail_silently=False)
        return True
    except Exception:  # noqa: BLE001 — a mail outage must not crash the task
        logger.warning('errors.alerts: could not send "%s"', subject, exc_info=True)
        return False


def _errors_link() -> str:
    from core.utils.site import site_base_url

    return f'{site_base_url().rstrip("/")}/dashboard/errors/'


def build_digest(hours: int = 24) -> tuple[int, str]:
    """``(server error count, email body)`` for the last ``hours``."""
    from core.errors.models import ErrorEvent

    since = timezone.now() - timedelta(hours=hours)
    window = ErrorEvent.objects.filter(created_at__gte=since)
    server = window.filter(kind=ErrorEvent.KIND_SERVER, level=ErrorEvent.LEVEL_ERROR)
    total = server.count()
    if not total:
        return 0, ''
    groups = (
        server.values('fingerprint')
        .annotate(n=Count('pk'), last=Max('created_at'))
        .order_by('-n', '-last')[:10]
    )
    lines = []
    for group in groups:
        sample = server.filter(fingerprint=group['fingerprint']).order_by('-created_at').first()
        message = (sample.message or '').replace('\n', ' ')[:160]
        where = f' on {sample.path}' if sample.path else ''
        lines.append(f'- {group["n"]}× {sample.exception_class}{where}: {message}')
    shown = sum(g['n'] for g in groups)
    more = f'\n…and {total - shown} more.' if total > shown else ''
    client = window.filter(kind=ErrorEvent.KIND_CLIENT).count()
    browser = f'\n\nBrowser-side errors in the same period: {client}.' if client else ''
    body = (
        f'{total} server error{"s" if total != 1 else ""} in the last {hours} hours, '
        'grouped by cause (most frequent first):\n\n'
        + '\n'.join(lines)
        + more
        + browser
        + f'\n\nDetails: {_errors_link()}\n'
    )
    return total, body


def send_digest(hours: int = 24) -> int:
    """Send the digest when there was at least one server error. Returns the count."""
    from core.utils.site import store_name

    total, body = build_digest(hours)
    if total:
        name = store_name() or 'Your store'
        send_alert(f'[{name}] {total} error{"s" if total != 1 else ""} in the last day', body)
    return total
