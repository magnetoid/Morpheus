---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/storefront_cache.py

Symbols in `core/storefront_cache.py`.

- L52 `StorefrontCacheMiddleware` (class) — Apply the merchant-configured Cache-Control to anonymous
- L56 `__init__(self, get_response)` (method)
- L59 `__call__(self, request)` (method)
- L67 `_maybe_set_header(self, request, response)` (method)
- L125 `_route_ttl(path: str, cfg: dict[str, Any])` (method)
- L135 `_storefront_config()` (method) — Read storefront PluginConfig — cached cheaply by the registry.
