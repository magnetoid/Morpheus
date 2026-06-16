---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/observability/services.py

Symbols in `plugins/installed/observability/services.py`.

- L30 `_truncate(ts: datetime, granularity: str)` (function)
- L40 `rollup(*, granularity: str='hour', lookback_hours: int=6)` (function) — Roll up OutboxEvent rows that landed in the last `lookback_hours` into
- L98 `record_error(*, source: str, message: str, stack_trace: str='', channel=None, metadata: dict | None=None)` (function) — Record an ErrorEvent. Fail-soft on DB outage.
- L121 `supported_metrics()` (function)
