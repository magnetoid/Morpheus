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

# plugins/installed/booking_marketplace/seo.py

Symbols in `plugins/installed/booking_marketplace/seo.py`.

- L55 `_route(request)` (function)
- L62 `on_seo_resolve_page(value, request=None, context=None, **kwargs)` (function) — SEO_RESOLVE_PAGE — claim this app's routes; return `value` untouched otherwise.
- L102 `on_seo_jsonld_graph(value, page=None, request=None, **kwargs)` (function) — SEO_JSONLD_GRAPH — add this page's entity (and its visible FAQ) to the graph.
- L130 `_entity_nodes(name: str, ctx: dict, url: str, request)` (function)
- L151 `_host_listings(vendor)` (function)
- L166 `on_vendor_listing_counts(value, **kwargs)` (function) — VENDOR_LISTING_COUNTS — add each host's active experiences, goods and stays.
- L188 `on_vendor_sections(value, vendor=None, request=None, **kwargs)` (function) — STOREFRONT_VENDOR_SECTIONS — the host's experiences, stays and local goods.
- L237 `on_search_path(value, request=None, **kwargs)` (function) — STOREFRONT_SEARCH_PATH — search lands where the inventory is.
