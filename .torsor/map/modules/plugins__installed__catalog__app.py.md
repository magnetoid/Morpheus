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

# plugins/installed/catalog/app.py

Symbols in `plugins/installed/catalog/app.py`.

- L14 `CatalogPlugin` (class)
- L21 `ready(self)` (method)
- L39 `on_restore_losses(self, value, since=None, **kwargs)` (method) — RESTORE_LOSSES: the products added or changed since the backup was made.
- L47 `on_brain_signals(self, value, **kwargs)` (method) — Merge the catalog content-gap slice into the Brain snapshot —
- L66 `on_dashboard_kpis(self, value, date_range=None, **kwargs)` (method) — Append the active-products KPI tile.
- L83 `on_dashboard_panels(self, value, date_range=None, **kwargs)` (method) — Fold the top-products panel into the home context.
- L92 `on_setup_steps(self, value, **kwargs)` (method) — Append the 'add your first product' first-run step.
- L107 `get_config_schema(self)` (method) — Store-wide image settings.
- L198 `contribute_agent_tools(self)` (method)
- L219 `contribute_settings_panel(self)` (method)
