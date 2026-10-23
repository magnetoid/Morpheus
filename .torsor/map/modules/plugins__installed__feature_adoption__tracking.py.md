---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/feature_adoption/tracking.py

Symbols in `plugins/installed/feature_adoption/tracking.py`.

- L41 `_counter_key(day: date, plugin: str, surface: str)` (function)
- L45 `_dirty_key(day: date)` (function)
- L49 `_incr(plugin: str, surface: str)` (function) — Bump today's counter for (plugin, surface) and note it as dirty.
- L74 `_second_segment(path: str)` (function)
- L81 `_segment_plugin_map()` (function) — Map the first path segment of custom dashboard mounts to their plugin.
- L99 `resolve_plugin(path: str)` (function) — Owning plugin for a ``/dashboard/…`` path, or ``None`` if unknown.
- L112 `track_dashboard_hit(request)` (function) — Context processor: count a dashboard visit against its owning plugin.
- L130 `track_agent_tool(value, tool: str='', **kwargs)` (function) — Filter subscriber: count a tool call by its (active-plugin) prefix.
- L152 `flush_counters(days_back: int=1)` (function) — Drain today's (and recent) cache counters into ``FeatureUsageDay``.
- L193 `compute_health(*, plugins_used: int, plugins_enabled: int, agent_calls: int, days_since_dashboard: int | None)` (function) — Pure install-health score (0–100) from three components.
- L219 `install_health()` (function) — Install-health score computed from the last 30 days of ``FeatureUsageDay``.
- L252 `adoption_matrix(days: int=90)` (function) — Per-plugin usage over 7/30/90-day windows + a daily series for sparklines.
- L299 `dashboard_kpis(value, **kwargs)` (function) — Append the install-health tile to the dashboard KPI row.
