---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/observability/services.py

Symbols in `plugins/installed/observability/services.py`.

- L29 `_truncate(ts: datetime, granularity: str)` (function)
- L39 `rollup(*, granularity: str='hour', lookback_hours: int=6)` (function) — Roll up OutboxEvent rows that landed in the last `lookback_hours` into
- L97 `record_error(*, source: str, message: str, stack_trace: str='', channel=None, metadata: dict | None=None)` (function) — Record an ErrorEvent. Fail-soft on DB outage.
- L120 `supported_metrics()` (function)
