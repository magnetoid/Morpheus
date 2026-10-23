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

# plugins/installed/agentic_checkout/feed.py

Symbols in `plugins/installed/agentic_checkout/feed.py`.

- L52 `_DefaultFeedSettings` (class) — Minimal stand-in for google_shopping's FeedSettings — only the fields
- L63 `_resolve_feed_settings()` (function)
- L72 `_price(raw: str)` (function) — ``'9.00 USD'`` → ``{'amount': 900, 'currency': 'USD'}`` (minor units,
- L91 `_seller(base: str)` (function)
- L103 `_variant(item: dict, *, seller: dict, option: str='')` (function) — One ``Variant`` from a google_shopping feed row.
- L140 `_product(base: dict, variants: list[dict], *, eligible: bool)` (function)
- L156 `_option_name(row: dict, base: dict)` (function) — The variant's own name: ``expand_variants`` appends it to the title.
- L166 `product_feed(request: HttpRequest)` (function) — GET /acp/feed.json — ACP product feed for active products.
