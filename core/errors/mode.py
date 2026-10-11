"""The detailed-capture switch (docs/plans/detailed-error-capture-2026-10.md).

``detailed_active()`` is called on hot paths (every WARNING log record, every
response), so it reads the one ``ErrorCaptureMode`` row at most once every
``_MEMO_S`` seconds per process. A switch flipped in the dashboard reaches the
web workers and the Celery worker within that time; it is a debugging aid, so
seconds of lag are fine and a per-call query is not.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta

logger = logging.getLogger('morpheus.errors')

_MEMO_S = 10.0
_lock = threading.Lock()
_memo: dict[str, object] = {'at': 0.0, 'until': None}

#: The windows offered on the error log page, in hours.
WINDOWS = (24, 168)
MAX_HOURS = 24 * 14


def _read_until() -> datetime | None:
    from core.errors.models import ErrorCaptureMode

    row = ErrorCaptureMode.objects.filter(pk=1).only('detailed_until').first()
    return row.detailed_until if row else None


def detailed_until() -> datetime | None:
    """When detailed capture ends, or None when it is off. Fail-soft."""
    from django.utils import timezone

    now = time.monotonic()
    with _lock:
        fresh = now - float(_memo['at']) < _MEMO_S
        until = _memo['until']
    if not fresh:
        try:
            until = _read_until()
        except Exception:  # noqa: BLE001 — no table yet, DB down: standard capture
            until = None
        with _lock:
            _memo['at'] = now
            _memo['until'] = until
    if until is None or until <= timezone.now():
        return None
    return until  # type: ignore[return-value]


def detailed_active() -> bool:
    return detailed_until() is not None


def forget() -> None:
    """Drop the memo, so this process reads the switch on its next check."""
    with _lock:
        _memo['at'] = 0.0
        _memo['until'] = None


def turn_on(hours: int, *, user=None) -> datetime:
    from django.utils import timezone

    from core.errors.models import ErrorCaptureMode

    hours = max(1, min(int(hours), MAX_HOURS))
    now = timezone.now()
    until = now + timedelta(hours=hours)
    ErrorCaptureMode.objects.update_or_create(
        pk=1,
        defaults={
            'detailed_until': until,
            'enabled_at': now,
            'enabled_by': user if getattr(user, 'is_authenticated', False) else None,
        },
    )
    forget()
    _audit('errors.detailed_capture_on', user, {'until': until.isoformat(), 'hours': hours})
    return until


def turn_off(*, user=None) -> None:
    from core.errors.models import ErrorCaptureMode

    ErrorCaptureMode.objects.update_or_create(pk=1, defaults={'detailed_until': None})
    forget()
    _audit('errors.detailed_capture_off', user, {})


def state() -> dict:
    """What the error log page shows about the switch."""
    from core.errors.models import ErrorCaptureMode

    row = ErrorCaptureMode.objects.select_related('enabled_by').filter(pk=1).first()
    until = detailed_until()
    by = ''
    if until and row and row.enabled_by_id:
        by = getattr(row.enabled_by, 'email', '') or getattr(row.enabled_by, 'username', '')
    return {
        'active': until is not None,
        'until': until,
        'since': row.enabled_at if (until and row) else None,
        'by': by,
    }


def _audit(event: str, user, metadata: dict) -> None:
    try:
        from core.audit.services import record

        record(event_type=event, actor=user, target='error_capture', metadata=metadata)
    except Exception:  # noqa: BLE001 — the switch works even if audit is down
        logger.warning('errors: audit of %s failed', event, exc_info=True)
