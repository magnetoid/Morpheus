"""JSON log formatter for production. One line per record, machine-friendly."""

from __future__ import annotations

import json
import logging
import time
import traceback


def redact_email(email: str) -> str:
    """email[:2] + '***@' + domain  →  'ma***@example.com'"""
    if not email or '@' not in email:
        return email or ''
    local, _, domain = email.partition('@')
    if len(local) <= 2:
        return f'{local[:1]}***@{domain}'
    return f'{local[:2]}***@{domain}'


# Keys in the structured log record `extra` dict whose values are emails and
# should be redacted before emission.
_EMAIL_KEYS = {'email', 'user_email', 'customer_email'}


_RESERVED = {
    'name',
    'msg',
    'args',
    'levelname',
    'levelno',
    'pathname',
    'filename',
    'module',
    'exc_info',
    'exc_text',
    'stack_info',
    'lineno',
    'funcName',
    'created',
    'msecs',
    'relativeCreated',
    'thread',
    'threadName',
    'processName',
    'process',
    'message',
    'asctime',
}


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON object.

    Includes `request_id` (from the request_id filter), `level`, `logger`,
    `module`, and any structured fields the caller passed via `extra=`.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            'ts': time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(record.created))
            + f'.{int(record.msecs):03d}Z',
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'msg': record.getMessage(),
            'request_id': getattr(record, 'request_id', '-'),
        }
        # Surface any extra= fields without leaking the LogRecord internals.
        for key, raw in record.__dict__.items():
            if key in _RESERVED or key.startswith('_'):
                continue
            if key in payload:
                continue
            # PII: redact emails in known email-bearing keys before emit.
            value = redact_email(raw) if key in _EMAIL_KEYS and isinstance(raw, str) else raw
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)

        if record.exc_info:
            payload['exc'] = ''.join(traceback.format_exception(*record.exc_info)).rstrip()

        return json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
