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

# core/models.py

Symbols in `core/models.py`.

- L12 `StoreSettings` (class) — Global store configuration singleton.
- L92 `__str__(self)` (method)
- L96 `get(cls, key: str, default=None)` (method)
- L107 `StoreChannel` (class) — A storefront channel. One Morpheus backend serves N channels — different
- L136 `__str__(self)` (method)
- L140 `resolve_for_request(cls, request)` (method) — Pick the best channel for `request` — by host, else default, else first.
- L152 `ProductChannelListing` (class) — Per-channel pricing + visibility for a Product.
- L186 `__str__(self)` (method)
- L190 `hash_api_key(raw: str)` (function) — SHA-256 of an API token, for hash-at-rest storage + constant lookup.
- L199 `APIKey` (class) — Law 2: Secure Core. Granular RBAC for headless clients and Remote Plugins.
- L225 `__str__(self)` (method)
- L228 `has_scope(self, scope: str)` (method)
- L231 `save(self, *args, **kwargs)` (method)
- L243 `WebhookEndpoint` (class) — Subscribes external services (Remote Plugins) to Morpheus Events.
- L260 `__str__(self)` (method)
- L264 `OutboxEvent` (class) — Implements the Transactional Outbox pattern.
- L290 `__str__(self)` (method)
- L294 `ExchangeRate` (class) — A snapshot rate from `base` → `quote` currency (e.g. USD → EUR).
- L314 `__str__(self)` (method)
- L318 `DeployEvent` (class) — One deploy of this store, written by ``manage.py safe_migrate`` before it
- L337 `__str__(self)` (method)
