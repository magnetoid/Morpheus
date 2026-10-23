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

# core/utils/cache.py

Symbols in `core/utils/cache.py`.

- L13 `cache_graphql_query(timeout=3600, key_prefix='gql')` (function) — Decorator for Strawberry GraphQL resolvers to cache responses in Redis.
- L43 `SmartCacheInvalidator` (class) — Subscribes to the Morpheus Event Bus to automatically invalidate
- L50 `bind_events()` (method)
- L81 `_clear_query_caches(reason: str)` (method)
- L90 `_clear_catalog_cache(**kwargs)` (method)
