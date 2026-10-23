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

# plugins/installed/analytics/services_anomaly.py

Symbols in `plugins/installed/analytics/services_anomaly.py`.

- L19 `_value(row)` (function)
- L26 `_baseline_rows(metric: str, target: date)` (function)
- L45 `detect_anomalies(*, day: date | None=None)` (function) — Scan watched metrics for `day` (default yesterday). Returns findings
- L100 `_notify(findings: list[dict])` (function) — Staff notification via notifications_center — best-effort.
