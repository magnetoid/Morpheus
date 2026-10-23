---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# api/middleware.py

Symbols in `api/middleware.py`.

- L21 `_cacheable_query(query: str)` (function) — True iff `query` is a pure query whose top-level fields are all public
- L47 `_vary_key(request)` (function) — The per-visitor axes an anonymous storefront response varies on. Folded
- L66 `GraphQLCacheMiddleware` (class) — Enterprise GraphQL Query Caching Middleware.
- L74 `__init__(self, get_response)` (method)
- L77 `__call__(self, request)` (method)
