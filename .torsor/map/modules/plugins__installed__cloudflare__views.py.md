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

# plugins/installed/cloudflare/views.py

Symbols in `plugins/installed/cloudflare/views.py`.

- L26 `_install_graphql_cache_rule(zone)` (function) — Idempotently install a CF Cache Rule that caches anonymous
- L74 `_trail(*items)` (function)
- L80 `overview(request)` (function) — Account list + last-purge feed. Entry point for the CF surface.
- L131 `account_sync(request, account_id)` (function) — Pull zones for one account from the CF API and upsert into our DB.
- L156 `zones_list(request)` (function) — List every zone known to Morpheus across all accounts.
- L176 `zone_detail(request, zone_id)` (function) — Per-zone dashboard: settings + recent purges + analytics summary.
- L336 `purge_form(request, zone_id)` (function) — Manual cache-purge UI: URL list, host list, or purge everything.
- L423 `analytics(request, zone_id)` (function) — Full analytics page for a zone (configurable window).
- L479 `invalidations_log(request)` (function) — Cross-zone purge audit log.
- L497 `dns_records(request, zone_id)` (function) — DNS records for a zone — list + add + delete.
- L560 `firewall_events(request, zone_id)` (function) — Recent WAF / firewall events (blocks, challenges, JS challenges).
