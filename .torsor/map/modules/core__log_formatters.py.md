---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/log_formatters.py

Symbols in `core/log_formatters.py`.

- L11 `redact_email(email: str)` (function) — email[:2] + '***@' + domain  →  'ma***@example.com'
- L52 `JsonFormatter` (class) — Emit each log record as a single JSON object.
- L59 `format(self, record: logging.LogRecord)` (method)
