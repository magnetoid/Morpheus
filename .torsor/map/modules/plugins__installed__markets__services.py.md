---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/markets/services.py

Symbols in `plugins/installed/markets/services.py`.

- L11 `_country_from_request(request)` (function) — Pick the visitor's country code.
- L29 `resolve_market(request)` (function) — Pick the active market for the request. ``None`` if markets
- L54 `price_for(*, product, market)` (function) — Return the Money price of `product` in `market`.
- L89 `market_context(request)` (function) — Used as a Django context processor — adds `active_market` and a
- L118 `current_channel(request)` (function) — Return the channel (Market) resolved for this request, or None.
- L126 `channel_scope(queryset, request=None, *, channel=None)` (function) — Apply per-channel filtering to a queryset, when meaningful.
- L160 `channel_pk(request)` (function) — Convenience: the active channel's PK as a string, or '' if none.
