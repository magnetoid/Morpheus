---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/markets/services.py

Symbols in `plugins/installed/markets/services.py`.

- L12 `_country_from_request(request)` (function) — Pick the visitor's country code.
- L30 `resolve_market(request)` (function) — Pick the active market for the request. ``None`` if markets
- L55 `price_for(*, product, market)` (function) — Return the Money price of `product` in `market`.
- L94 `market_context(request)` (function) — Used as a Django context processor — adds `active_market` and a
- L124 `current_channel(request)` (function) — Return the channel (Market) resolved for this request, or None.
- L132 `channel_scope(queryset, request=None, *, channel=None)` (function) — Apply per-channel filtering to a queryset, when meaningful.
- L166 `channel_pk(request)` (function) — Convenience: the active channel's PK as a string, or '' if none.
