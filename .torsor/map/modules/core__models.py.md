---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/models.py

Symbols in `core/models.py`.

- L11 `StoreSettings` (class) — Global store configuration singleton.
- L44 `__str__(self)` (method)
- L48 `get(cls, key: str, default=None)` (method)
- L59 `StoreChannel` (class) — A storefront channel. One Morpheus backend serves N channels — different
- L88 `__str__(self)` (method)
- L92 `resolve_for_request(cls, request)` (method) — Pick the best channel for `request` — by host, else default, else first.
- L104 `ProductChannelListing` (class) — Per-channel pricing + visibility for a Product.
- L138 `__str__(self)` (method)
- L142 `APIKey` (class) — Law 2: Secure Core. Granular RBAC for headless clients and Remote Plugins.
- L159 `__str__(self)` (method)
- L162 `has_scope(self, scope: str)` (method)
- L165 `save(self, *args, **kwargs)` (method)
- L173 `WebhookEndpoint` (class) — Subscribes external services (Remote Plugins) to Morpheus Events.
- L190 `__str__(self)` (method)
- L194 `OutboxEvent` (class) — Implements the Transactional Outbox pattern.
- L217 `__str__(self)` (method)
- L221 `ExchangeRate` (class) — A snapshot rate from `base` → `quote` currency (e.g. USD → EUR).
- L242 `__str__(self)` (method)
