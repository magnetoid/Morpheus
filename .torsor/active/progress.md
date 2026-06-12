---
type: progress
status: active
tags:
- active
links: []
created: '2026-06-12T04:51:11'
updated: '2026-06-12T04:51:11'
---

# Progress

Discovered inventory/demand_forecast.py already implements the predictive engine (forecast_all → velocity from StockMovement movement_type='sale', days_until_stockout, reorder_recommended, suggested_reorder_qty; ForecastRow dataclass; _severity_for) but it is DEAD CODE — never called, no schedule, no dashboard, no agent tool, no tests. Feature = wire it up as a stateful alert-delivery layer. Verified all 6 integration points via workflow: (1) merchant alerts via notifications_center.services.notify_all_staff(*, kind,title,body='',action_url='',icon='bell')->int, keyword-only, no built-in dedup (so a StockoutAlert model handles dedup). (2) beat schedule: self.register_celery_beat(name, {'task','schedule'}) in plugin.ready(); schedule = int seconds or celery crontab; setdefault (operator-overridable). (3) DASHBOARD_HOME_PANELS is a filter where each plugin folds data into a dict, but panel KEYS map to hardcoded sections in admin_dashboard/home.html — adding a NEW panel there would violate the plugin contract. (4) agent tool: @tool(name='inventory.stockout_forecast', scopes=['inventory.read'], schema=...) -> ToolResult(output,display); register in contribute_agent_tools. (5) models: UUID PK, StockMovement.quantity_change (negative for sales), movement_type='sale'; next migration after latest in inventory/migrations/. Planned components: StockoutAlert model+migration, sync_stockout_alerts() reconciler in demand_forecast.py, inventory.run_stockout_forecast daily beat task firing notify_all_staff for NEWLY opened alerts only, a dashboard surface, inventory.stockout_forecast agent tool, tests.
