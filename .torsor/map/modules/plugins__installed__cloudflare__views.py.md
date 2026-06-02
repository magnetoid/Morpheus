---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/cloudflare/views.py

Symbols in `plugins/installed/cloudflare/views.py`.

- L20 `_install_graphql_cache_rule(zone)` (function) — Idempotently install a CF Cache Rule that caches anonymous
- L68 `_trail(*items)` (function)
- L79 `overview(request)` (function) — Account list + last-purge feed. Entry point for the CF surface.
- L129 `account_sync(request, account_id)` (function) — Pull zones for one account from the CF API and upsert into our DB.
- L153 `zones_list(request)` (function) — List every zone known to Morpheus across all accounts.
- L172 `zone_detail(request, zone_id)` (function) — Per-zone dashboard: settings + recent purges + analytics summary.
- L333 `purge_form(request, zone_id)` (function) — Manual cache-purge UI: URL list, host list, or purge everything.
- L419 `analytics(request, zone_id)` (function) — Full analytics page for a zone (configurable window).
- L474 `invalidations_log(request)` (function) — Cross-zone purge audit log.
- L491 `dns_records(request, zone_id)` (function) — DNS records for a zone — list + add + delete.
- L553 `firewall_events(request, zone_id)` (function) — Recent WAF / firewall events (blocks, challenges, JS challenges).
