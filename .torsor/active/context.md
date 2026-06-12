---
type: active-context
status: active
tags:
- active
links: []
created: '2026-06-12T04:51:11'
updated: '2026-06-12T04:51:11'
---

# Active Context

## Current focus
Building "Predictive Stockout Alerts" as an enhancement to the inventory plugin (user confirmed: NOT a separate app). Brainstorming → spec phase. Scope: alerts + visibility.

## Open questions
Dashboard visibility surface must stay contract-clean: rendering a NEW DASHBOARD_HOME_PANELS panel needs an admin_dashboard/home.html edit (contract violation). Resolve to one of: (a) enrich inventory's EXISTING low_stock panel with predictive at-risk data (no new template), or (b) a dedicated inventory-owned DashboardPage (inventory fully owns page+template). Leaning (b) or (a). Also: confirm next inventory migration number; decide dedup/uniqueness (one OPEN StockoutAlert per variant).
