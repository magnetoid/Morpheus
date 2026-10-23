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

# plugins/installed/analytics/models.py

Symbols in `plugins/installed/analytics/models.py`.

- L28 `AnalyticsSession` (class) — One visitor session, identified by a long-lived analytics cookie.
- L78 `AnalyticsEvent` (class) — Append-only event log.
- L161 `DailyMetric` (class) — One row per (day, metric_name, dimension_value).
- L185 `FunnelDefinition` (class) — A named ordered list of event names.
- L197 `CustomEventConfig` (class) — No-code configuration for business-specific metric tracking.
- L215 `AnalyticsExport` (class) — Scheduled or one-off analytics exports.
- L232 `AdSpendSnapshot` (class) — Ad spend per (day, channel), collected nightly from channel plugins via the
- L246 `__str__(self)` (method)
