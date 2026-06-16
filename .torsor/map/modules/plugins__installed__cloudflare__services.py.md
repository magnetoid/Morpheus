---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/cloudflare/services.py

Symbols in `plugins/installed/cloudflare/services.py`.

- L35 `CloudflareError` (class) — Raised when the Cloudflare API returns a non-success response.
- L39 `CloudflareClient` (class) — Thin Cloudflare API v4 client, scoped to a single account.
- L49 `__init__(self, *, api_token: str, session: Any | None=None)` (method)
- L53 `_request(self, method: str, path: str, *, payload: dict | None=None, params: dict | None=None)` (method)
- L77 `_get(self, path: str, params: dict | None=None)` (method)
- L80 `_post(self, path: str, payload: dict | None)` (method)
- L83 `_patch(self, path: str, payload: dict | None)` (method)
- L88 `verify_token(self)` (method) — Confirms the API token is valid and returns its scope summary.
- L92 `list_accounts(self)` (method)
- L97 `list_zones(self, account_id: str | None=None)` (method)
- L103 `get_zone(self, zone_id: str)` (method)
- L106 `get_zone_settings(self, zone_id: str)` (method)
- L109 `patch_zone_setting(self, zone_id: str, setting_id: str, value: Any)` (method)
- L114 `get_analytics_dashboard(self, zone_id: str, since: str='-10080', until: str='0')` (method) — Dashboard summary (requests, bandwidth, threats, cache stats).
- L129 `list_firewall_events(self, zone_id: str, limit: int=50)` (method)
- L136 `list_dns_records(self, zone_id: str)` (method)
- L139 `create_dns_record(self, zone_id: str, *, type: str, name: str, content: str, ttl: int=1, proxied: bool=False)` (method) — Create a new DNS record. ttl=1 means 'auto' per CF docs.
- L161 `delete_dns_record(self, zone_id: str, record_id: str)` (method)
- L166 `get_bot_fight_mode(self, zone_id: str)` (method)
- L169 `patch_bot_fight_mode(self, zone_id: str, enabled: bool)` (method)
- L180 `get_tiered_cache(self, zone_id: str)` (method) — Tiered Cache (smart topology) status.
- L184 `patch_tiered_cache(self, zone_id: str, value: str)` (method) — value: 'on' / 'off' — flips smart-topology Tiered Cache.
- L191 `get_cache_reserve(self, zone_id: str)` (method) — Cache Reserve status. Eligible objects need Content-Length + TTL ≥ 10h.
- L195 `patch_cache_reserve(self, zone_id: str, value: str)` (method) — value: 'on' / 'off'. ALWAYS pair with Tiered Cache to keep write costs down.
- L202 `get_argo_smart_routing(self, zone_id: str)` (method)
- L205 `patch_argo_smart_routing(self, zone_id: str, value: str)` (method)
- L210 `get_cache_ruleset(self, zone_id: str)` (method) — Read the http_request_cache_settings ruleset entrypoint.
- L214 `put_cache_ruleset(self, zone_id: str, rules: list[dict])` (method) — Replace the entire cache-settings ruleset with `rules`.
- L224 `purge_cache(self, zone_id: str, *, urls: Sequence[str] | None=None, tags: Sequence[str] | None=None, hosts: Sequence[str] | None=None, purge_everything: bool=False)` (method)
- L248 `_client_for(zone)` (function)
- L252 `purge_urls(*, zone, urls: Iterable[str], triggered_by: str='', client: CloudflareClient | None=None)` (function)
- L268 `purge_tags(*, zone, tags: Iterable[str], triggered_by: str='', client: CloudflareClient | None=None)` (function)
- L284 `purge_everything(*, zone, triggered_by: str='', client: CloudflareClient | None=None)` (function)
- L299 `_record_purge(*, zone, scope, targets, triggered_by, client)` (function)
- L348 `sync_zones(account)` (function) — Pull every zone the account's token can see from the CF API and
- L384 `zone_settings_map(zone)` (function) — Return zone settings as `{setting_id: value}` for easy template
- L392 `patch_zone_setting(zone, setting_id: str, value: Any)` (function) — Toggle / set one zone-level feature. Returns the API response.
- L398 `analytics_summary(zone, days: int=7)` (function) — Return a flat summary of the dashboard metrics over the last N
- L420 `purge_for_product_update(product)` (function) — Auto-purge cache for any zone with `auto_purge_on_product_update=True`.
- L463 `purge_for_category_update(category)` (function) — Tag-based companion to the URL-based hook in plugin.py.
