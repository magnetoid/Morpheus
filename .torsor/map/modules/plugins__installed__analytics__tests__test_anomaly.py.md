---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/analytics/tests/test_anomaly.py

Symbols in `plugins/installed/analytics/tests/test_anomaly.py`.

- L15 `_seed(metric: str, values: list[int])` (function) — values[-1] is 'yesterday'; earlier entries step back one day each.
- L22 `AnomalyTests` (class)
- L23 `test_flat_data_is_quiet(self)` (method)
- L27 `test_crash_fires(self)` (method)
- L35 `test_idempotent_per_metric_day(self)` (method)
- L41 `test_too_little_history_is_quiet(self)` (method)
