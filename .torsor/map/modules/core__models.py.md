---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# core/models.py

Symbols in `core/models.py`.

- L9 `StoreSettings` (class) — Global store configuration singleton.
- L39 `__str__(self)` (method)
- L43 `get(cls, key: str, default=None)` (method)
- L52 `StoreChannel` (class) — A storefront channel. One Morpheus backend serves N channels — different
- L77 `__str__(self)` (method)
- L81 `resolve_for_request(cls, request)` (method) — Pick the best channel for `request` — by host, else default, else first.
- L93 `ProductChannelListing` (class) — Per-channel pricing + visibility for a Product.
- L123 `__str__(self)` (method)
- L126 `APIKey` (class) — Law 2: Secure Core. Granular RBAC for headless clients and Remote Plugins.
- L138 `__str__(self)` (method)
- L141 `has_scope(self, scope: str)` (method)
- L144 `save(self, *args, **kwargs)` (method)
- L150 `WebhookEndpoint` (class) — Subscribes external services (Remote Plugins) to Morpheus Events.
- L162 `__str__(self)` (method)
- L165 `OutboxEvent` (class) — Implements the Transactional Outbox pattern.
- L186 `__str__(self)` (method)
- L190 `ExchangeRate` (class) — A snapshot rate from `base` → `quote` currency (e.g. USD → EUR).
- L211 `__str__(self)` (method)
