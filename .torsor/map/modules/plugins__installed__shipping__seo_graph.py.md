---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/shipping/seo_graph.py

Symbols in `plugins/installed/shipping/seo_graph.py`.

- L24 `on_seo_jsonld_graph(value, page=None, request=None, **kwargs)` (function) — `SEO_JSONLD_GRAPH` subscriber: add shipping to the product's offer.
- L38 `shipping_details(*, currency: str='USD')` (function) — `OfferShippingDetails` for the cheapest active rate in each zone.
- L67 `_details_for(rate, currency: str)` (function)
- L106 `_rate_amount(rate)` (function) — The advertised price of this rate, or None when it cannot be known.
- L131 `_delivery_time(rate)` (function)
- L150 `_product_offer(graph)` (function) — The offer on the graph's Product node, when the page has one.
