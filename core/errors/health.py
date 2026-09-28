"""Nightly health check: can this store still sell, and does it tell anyone?

Each app contributes the checks only it can make through the ``HEALTH_CHECKS``
filter (payments: a payment method is offered; orders: a cart can be priced;
storefront: the public pages load). Core adds its own: outgoing email is set up
and the order-email templates load. Every one of those broke on a live store in
2026 without anyone being told; a failure is now recorded as an ErrorEvent and
emailed the same night.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.errors.health')

# Contains "monitor", which core.utils.crawlers treats as a bot, so these
# requests are not counted as shoppers.
USER_AGENT = 'MorpheusHealthCheck/1.0 (monitor)'


def fetch_failures(paths: list[str]) -> list[str]:
    """GET each path on the public site (through the CDN, like a shopper); list failures."""
    import requests

    from core.utils.site import site_base_url

    base = site_base_url().rstrip('/')
    failures = []
    for path in paths:
        try:
            response = requests.get(
                base + path, timeout=20, headers={'User-Agent': USER_AGENT}, allow_redirects=True
            )
            if response.status_code >= 400:
                failures.append(f'{path} → {response.status_code}')
        except requests.RequestException as e:
            failures.append(f'{path} → {type(e).__name__}')
    return failures


# Every order email core sends (core.emails.handlers).
_EMAIL_TEMPLATES = (
    'order_placed', 'order_paid', 'order_fulfilled', 'order_cancelled',
    'refund_issued', 'digital_download', 'welcome',
)  # fmt: skip


def _core_checks() -> list[dict]:
    from django.template.loader import get_template

    from core.email import smtp_configured

    missing = []
    for base in _EMAIL_TEMPLATES:
        try:
            get_template(f'emails/{base}.txt')
        except Exception:  # noqa: BLE001
            missing.append(base)
    email_ok = smtp_configured()
    return [
        {
            'name': 'Outgoing email is set up',
            'ok': email_ok,
            'detail': ''
            if email_ok
            else 'Emails are written to the log instead of being sent: no SMTP server '
            'is configured (Settings → Notifications).',
        },
        {
            'name': 'Order email templates load',
            'ok': not missing,
            'detail': f'Missing: {", ".join(missing)}' if missing else '',
        },
    ]


def run_checks() -> list[dict]:
    """Core checks plus every app's ``HEALTH_CHECKS`` contribution."""
    from core.hooks import MorpheusEvents, hook_registry

    results = _core_checks()
    try:
        results = hook_registry.filter(MorpheusEvents.HEALTH_CHECKS, results) or results
    except Exception:  # noqa: BLE001 — one broken contributor must not hide the rest
        logger.warning('health: HEALTH_CHECKS filter failed', exc_info=True)
    return [r for r in results if isinstance(r, dict) and r.get('name')]


def run_and_report() -> list[dict]:
    """Run every check; record and email the failures. Returns the failures."""
    from core.errors.alerts import _errors_link, send_alert
    from core.errors.services import record_message
    from core.utils.site import store_name

    failed = [r for r in run_checks() if not r.get('ok')]
    for r in failed:
        record_message(
            f'Health check failed: {r["name"]}. {r.get("detail", "")}'.strip(),
            level='error',
            source='health_check',
            exception_class='HealthCheckFailed',
        )
    if failed:
        name = store_name() or 'Your store'
        body = (
            'The nightly health check found a problem that can stop this store from '
            'selling or from telling customers about their orders:\n\n'
            + '\n'.join(f'- {r["name"]}: {r.get("detail") or "failed"}' for r in failed)
            + f'\n\nError log: {_errors_link()}\n'
        )
        send_alert(f'[{name}] Health check failed ({len(failed)})', body)
    return failed
