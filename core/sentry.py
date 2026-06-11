"""Sentry SDK bootstrap.

No-op when `SENTRY_DSN` isn't set, so dev environments stay quiet. When
configured, scrubs auth/secret headers from every event before sending.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger('morpheus.sentry')

# Header keys we should never ship to Sentry, even via `request.headers`.
_SCRUB_HEADERS = {
    'authorization',
    'cookie',
    'x-agent-token',
    'x-shopify-access-token',
    'x-shopify-shop-domain',
    'x-csrftoken',
    'stripe-signature',
}
# Body-key fragments we also want to scrub from breadcrumbs / error contexts.
_SCRUB_BODY_FRAGMENTS = (
    'password',
    'secret',
    'token',
    'api_key',
    'apikey',
    'credit',
    'card',
)


def _scrub_headers(headers: dict[str, Any] | None) -> dict[str, Any] | None:
    if not headers:
        return headers
    out = {}
    for k, v in headers.items():
        if k.lower() in _SCRUB_HEADERS:
            out[k] = '[scrubbed]'
        else:
            out[k] = v
    return out


def _scrub_data(data: Any) -> Any:
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            lk = str(k).lower()
            if any(frag in lk for frag in _SCRUB_BODY_FRAGMENTS):
                out[k] = '[scrubbed]'
            else:
                out[k] = _scrub_data(v)
        return out
    if isinstance(data, list):
        return [_scrub_data(item) for item in data]
    return data


def _before_send(event: dict, hint: dict) -> dict | None:
    """Sentry hook: redact secrets before the event leaves the process."""
    request = event.get('request') or {}
    request['headers'] = _scrub_headers(request.get('headers'))
    request['data'] = _scrub_data(request.get('data'))
    request['cookies'] = '[scrubbed]'
    event['request'] = request
    if event.get('extra'):
        event['extra'] = _scrub_data(event['extra'])
    return event


def init_sentry() -> None:
    dsn = os.getenv('SENTRY_DSN')
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError as e:
        logger.warning('sentry: SDK not installed, skipping init: %s', e)
        return
    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv('SENTRY_ENVIRONMENT', os.getenv('DJANGO_ENV', 'production')),
            release=os.getenv('SENTRY_RELEASE', os.getenv('GIT_SHA', '')),
            integrations=[
                DjangoIntegration(transaction_style='url'),
                CeleryIntegration(monitor_beat_tasks=True),
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            ],
            traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.0')),
            profiles_sample_rate=float(os.getenv('SENTRY_PROFILES_SAMPLE_RATE', '0.0')),
            send_default_pii=False,
            before_send=_before_send,
        )
        logger.info('Sentry initialized for env=%s', os.getenv('SENTRY_ENVIRONMENT', '?'))
    except Exception as e:  # noqa: BLE001 — observability must never break boot
        logger.error('sentry: init failed: %s', e, exc_info=True)
