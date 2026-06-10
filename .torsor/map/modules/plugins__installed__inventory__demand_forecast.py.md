---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/inventory/demand_forecast.py

Symbols in `plugins/installed/inventory/demand_forecast.py`.

- L52 `ForecastRow` (class) — One forecast per variant.
- L66 `forecast_all(*, window_days: int=DEFAULT_WINDOW_DAYS, threshold_days: int=DEFAULT_REORDER_THRESHOLD_DAYS, reorder_multiplier: float=DEFAULT_REORDER_MULTIPLIER)` (function) — Compute forecast rows for every tracked variant.
- L149 `emit_reorder_signals(*, window_days: int=DEFAULT_WINDOW_DAYS, threshold_days: int=DEFAULT_REORDER_THRESHOLD_DAYS)` (function) — Feed reorder candidates into the self-improvement signal bus.
- L204 `_variant_label(variant)` (function)
- L212 `_severity_for(row: ForecastRow)` (function) — Higher severity = closer to stockout.
- L230 `projected_lost_revenue_if_no_reorder(row: ForecastRow, unit_price: Decimal)` (function) — Naive: window_days × velocity × unit_price, capped by current stock.
