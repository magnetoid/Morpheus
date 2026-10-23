---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/brain/log_handler.py

Symbols in `core/brain/log_handler.py`.

- L39 `ErrorEventLogHandler` (class) — Record ERROR+ LogRecords into observability.ErrorEvent for the Brain.
- L42 `__init__(self, level: int=logging.ERROR)` (method)
- L48 `emit(self, record: logging.LogRecord)` (method)
- L61 `_handle(self, record: logging.LogRecord)` (method)
- L107 `_warnings_wanted(record: logging.LogRecord)` (method) — WARNING records are kept only while detailed capture is on.
- L120 `_throttled(self, fp: str)` (method)
