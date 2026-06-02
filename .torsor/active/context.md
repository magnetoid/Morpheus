---
type: active-context
status: active
tags:
- active
links: []
created: '2026-06-02T21:48:22'
updated: '2026-06-02T21:48:22'
---

# Active Context

## Current focus
Settings de-duplication (ADR 0003) is underway. Shipping is merged to one page (live). Remaining duplicate settings surfaces are audited + ready to merge using the proven shipping pattern (combined view + one template + delete old templates + redirect old URLs + nav to one entry + tests). Best done in a fresh session — these are live-CRUD dashboard rewrites.

## Open questions
De-dup merge backlog (ranked, each in its OWNING plugin, mirror the shipping merge): (1) TAX — tax/plugin.py:99-118 two pages 'Tax regions'+'Tax rates' (tax/dashboard.py regions()+rates(), templates regions.html+rates.html) → ONE 'Tax' page; tax/dashboard.py rate logic uses _create_rate/_edit_rate/_delete_rate helpers, regions() inlines its CRUD. (2) SHIPPING panel — shipping/plugin.py:144 SettingsPanel 'Shipping' still exists alongside the merged page; fold carrier-config schema into the Shipping page as a 3rd section + drop the panel. (3) CLOUDFLARE — cloudflare/plugin.py:37 DashboardPage + :74 SettingsPanel both 'Cloudflare' (developer); keep one. (4) PAYMENTS — payments/plugin.py:132 + advanced_payments/plugin.py:94 two panels under category 'payments'; unify (advanced_payments toggles into the payments panel) + consider a single Payments page. LEAVE AI (ai_assistant + ai_content panels are distinct concerns/plugins, not true duplication). Also still open: Asset Part B (WP product media picker); disable the Test gateway after testing.
