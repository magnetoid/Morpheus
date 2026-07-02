"""Bridge application ERROR logs into the Morpheus Brain's signal pipeline.

Without this, the self-improvement `error_log` collector only sees errors that
some code explicitly recorded via ``observability.record_error()`` — app
exceptions logged through the normal logging stream never become signals, so the
Brain's Errors tab + AI analysis can't see them.

This ``logging.Handler`` records ERROR+ ``LogRecord``s as ``observability``
``ErrorEvent`` rows (the table the ``error_log`` collector polls → ``SiSignal``
→ Brain). It is FAIL-SOFT (never raises), LOOP-SAFE (reentrancy guard + a
denylist of its own subsystem's loggers), THROTTLED (one DB write per
fingerprint per minute), and BOOT-SAFE (no-op until the app registry is ready).
It writes only on ERROR+, so it never touches the request hot path for warnings.

NB: there are two ``record_error`` functions — ``core.errors.services`` writes a
DIFFERENT table the collector does NOT read. We deliberately use
``plugins.installed.observability.services.record_error``.
"""

from __future__ import annotations

import logging
import threading
import time

# Never record logs emitted by our own write path (would loop) or the noisy
# DB-query logger.
_LOGGER_DENYLIST = (
    'morpheus.observability',
    'morpheus.errors',
    'morpheus.self_improvement',
    'morpheus.brain',
    'django.db.backends',
)
_THROTTLE_TTL = 60.0  # seconds a fingerprint is suppressed
_THROTTLE_MAX = 512  # cap the in-process dedup dict


class ErrorEventLogHandler(logging.Handler):
    """Record ERROR+ LogRecords into observability.ErrorEvent for the Brain."""

    def __init__(self, level: int = logging.ERROR) -> None:
        super().__init__(level=level)
        self._reentrant = threading.local()
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(self._reentrant, 'active', False):
            return
        if record.name.startswith(_LOGGER_DENYLIST):
            return
        try:
            self._reentrant.active = True
            self._handle(record)
        except Exception:  # noqa: BLE001, S110 — logging must never raise
            pass
        finally:
            self._reentrant.active = False

    def _handle(self, record: logging.LogRecord) -> None:
        from django.apps import apps

        if not apps.ready:
            return
        # Error capture is a core system (ADR 0025) — record into core.errors.
        from core.errors.services import record_error, record_message

        msg = record.getMessage()
        # Lead with the exception class so the collector's class-extraction works.
        if record.exc_info and record.exc_info[0] is not None:
            message = f'{record.exc_info[0].__name__}: {msg}'
        else:
            message = msg

        fp = f'{record.name}|{record.module}:{record.lineno}|{message.split(":", 1)[0][:80]}'
        if self._throttled(fp):
            return

        level = record.levelname.lower()
        level = level if level in ('error', 'warning', 'info') else 'error'
        meta = {
            'logger': record.name,
            'level': record.levelname,
            'request_id': getattr(record, 'request_id', '') or '',
            'module': record.module,
            'lineno': record.lineno,
        }
        source = f'log:{record.name}'[:40]
        # A live exception → frame-based fingerprint via record_error; otherwise
        # the pre-formatted message path.
        exc = record.exc_info[1] if (record.exc_info and record.exc_info[1] is not None) else None
        if exc is not None:
            record_error(exc, kind='server', level=level, extra={**meta, 'source': source})
        else:
            record_message(message, kind='server', level=level, source=source, extra=meta)

    def _throttled(self, fp: str) -> bool:
        now = time.monotonic()
        with self._lock:
            last = self._seen.get(fp)
            if last is not None and (now - last) < _THROTTLE_TTL:
                return True
            if len(self._seen) >= _THROTTLE_MAX:
                self._seen.clear()
            self._seen[fp] = now
        return False
