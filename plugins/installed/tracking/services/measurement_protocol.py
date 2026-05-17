"""GA4 Measurement Protocol v2 — server-side event firing.

Every server-side hit goes through ``send_event()`` which:

1. Loads the singleton ``TrackingSettings`` (and short-circuits to
   ``status='disabled'`` if server-side firing or this event is off).
2. POSTs a JSON body to ``https://www.google-analytics.com/mp/collect``
   (or the region-specific endpoint) with the merchant's measurement
   ID + API secret.
3. Records the attempt as a ``GA4EventLog`` row regardless of success.

Required-on-every-request per the 2026 MP v2 spec:
* ``client_id`` — anonymous device identifier (we mint a UUID when we
  don't have a real ``_ga`` cookie; this still lets GA group hits
  into a synthetic session).
* per-event ``session_id`` and ``engagement_time_msec`` — without
  these the hit lands in DebugView but never in standard reports.
* ``consent`` object — Consent Mode v2 signals.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any
from urllib import request as _urlrequest

from django.utils import timezone

logger = logging.getLogger('morpheus.tracking')

_GLOBAL_ENDPOINT = 'https://www.google-analytics.com/mp/collect'
_EU_ENDPOINT = 'https://region1.google-analytics.com/mp/collect'


def _endpoint(region: str) -> str:
    return _EU_ENDPOINT if region == 'eu' else _GLOBAL_ENDPOINT


def _new_client_id() -> str:
    """Synthetic GA-format client_id when we have nothing real."""
    return f'{uuid.uuid4().int & ((1 << 32) - 1)}.{int(timezone.now().timestamp())}'


def _is_duplicate(settings_row, event_name: str, transaction_id: str,
                  client_id: str) -> bool:
    """Look back inside the dedup window for a matching SENT row."""
    from datetime import timedelta
    from plugins.installed.tracking.models import GA4EventLog

    strategy = settings_row.dedup_strategy or 'transaction_id'
    if strategy == 'off':
        return False
    cutoff = timezone.now() - timedelta(minutes=max(int(settings_row.dedup_window_minutes or 60), 1))
    qs = GA4EventLog.objects.filter(
        event_name=event_name, fired_at__gte=cutoff, status=GA4EventLog.STATUS_SENT,
    )
    if strategy == 'transaction_id' and transaction_id:
        return qs.filter(transaction_id=transaction_id).exists()
    if strategy == 'client_window' and client_id:
        return qs.filter(client_id=client_id).exists()
    return False


def send_event(
    *,
    event_name: str,
    params: dict[str, Any],
    client_id: str = '',
    session_id: str = '',
    user_id: str = '',
    consent: dict[str, str] | None = None,
    transaction_id: str = '',
) -> 'GA4EventLog':
    """Fire one GA4 event server-side. Returns the audit row.

    Never raises — failures are persisted as ``status='error'``.
    """
    from plugins.installed.tracking.models import GA4EventLog, TrackingSettings

    s = TrackingSettings.get_solo()

    if not s.server_side_enabled:
        return GA4EventLog.objects.create(
            event_name=event_name,
            transaction_id=transaction_id,
            client_id=client_id,
            session_id=session_id,
            user_id=user_id,
            payload={'params': params},
            status=GA4EventLog.STATUS_DISABLED,
            error_message='server_side_enabled=False',
        )

    if not s.event_enabled(event_name):
        return GA4EventLog.objects.create(
            event_name=event_name,
            transaction_id=transaction_id,
            client_id=client_id,
            session_id=session_id,
            user_id=user_id,
            payload={'params': params},
            status=GA4EventLog.STATUS_DISABLED,
            error_message=f'event_firing[{event_name}]=False',
        )

    if not s.measurement_id or not s.api_secret:
        return GA4EventLog.objects.create(
            event_name=event_name,
            transaction_id=transaction_id,
            client_id=client_id,
            session_id=session_id,
            user_id=user_id,
            payload={'params': params},
            status=GA4EventLog.STATUS_ERROR,
            error_message='measurement_id or api_secret not configured',
        )

    if _is_duplicate(s, event_name, transaction_id, client_id):
        return GA4EventLog.objects.create(
            event_name=event_name,
            transaction_id=transaction_id,
            client_id=client_id,
            session_id=session_id,
            user_id=user_id,
            payload={'params': params},
            status=GA4EventLog.STATUS_DEDUPED,
        )

    cid = client_id or _new_client_id()
    sid = session_id or str(int(timezone.now().timestamp()))

    # Per-event required parameters per the 2026 MP v2 spec.
    event_params = dict(params or {})
    event_params.setdefault('session_id', sid)
    event_params.setdefault('engagement_time_msec', 100)

    body: dict[str, Any] = {
        'client_id': cid,
        'events': [{'name': event_name, 'params': event_params}],
    }
    if user_id:
        body['user_id'] = user_id
    body['consent'] = consent or {
        # Default to denied — this is the GDPR-safe posture; Google's
        # Consent Mode v2 server-side will still produce modeled
        # aggregates for opted-out visitors.
        'ad_user_data': 'DENIED',
        'ad_personalization': 'DENIED',
    }

    url = _endpoint(s.region) + f'?measurement_id={s.measurement_id}&api_secret={s.api_secret}'
    if s.debug_mode:
        url += '&debug_mode=1'

    status_code = None
    response_body = ''
    error_message = ''
    try:
        req = _urlrequest.Request(
            url,
            data=json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json; charset=utf-8',
                     'User-Agent': 'Morpheus-Tracking/1.0'},
            method='POST',
        )
        with _urlrequest.urlopen(req, timeout=6) as resp:
            status_code = resp.status
            response_body = (resp.read() or b'').decode('utf-8', errors='ignore')[:2000]
    except Exception as exc:  # noqa: BLE001 — never propagate
        error_message = str(exc)[:400]
        logger.warning('tracking.mp: POST failed for %s: %s', event_name, exc)

    return GA4EventLog.objects.create(
        event_name=event_name,
        transaction_id=transaction_id,
        client_id=cid,
        session_id=sid,
        user_id=user_id,
        payload=body,
        response_status=status_code,
        response_body=response_body,
        status=(GA4EventLog.STATUS_SENT if status_code and 200 <= status_code < 300 else GA4EventLog.STATUS_ERROR),
        error_message=error_message,
    )
