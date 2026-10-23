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

# plugins/installed/agent_core/app.py

Symbols in `plugins/installed/agent_core/app.py`.

- L81 `AgentCorePlugin` (class)
- L102 `ready(self)` (method)
- L121 `on_dashboard_panels(self, value, date_range=None, **kwargs)` (method) — Fold active-agent and recent-run counts into ai_summary.
- L149 `on_activity_feed(self, value, limit=20, **kwargs)` (method) — Fold recent agent runs into the dashboard home feed
- L173 `_register_beat_schedule(self)` (method)
- L215 `contribute_agent_tools(self)` (method)
- L220 `contribute_agents(self)` (method)
- L225 `contribute_storefront_blocks(self)` (method)
- L231 `contribute_dashboard_pages(self)` (method)
- L316 `contribute_settings_panel(self)` (method)
- L331 `get_config_schema(self)` (method)
