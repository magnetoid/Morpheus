---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/trust_signals/services.py

Symbols in `plugins/installed/trust_signals/services.py`.

- L30 `collect_trust_data(product, *, config: dict | None=None)` (function) — Single entry point — returns everything the template needs.
- L60 `_get_rating(product, cfg: dict)` (function) — Returns {avg, count, stars_filled, stars_half, stars_empty} or
- L105 `_get_verified_share(product)` (function) — Returns {percent, total} or None if total is too low.
- L143 `_get_recent_purchases(product, cfg: dict)` (function) — Returns {count, window_hours, plural_label} or None if below threshold.
- L189 `_plural_window_label(hours: int)` (function)
- L212 `_order_item_model()` (function) — Lazy resolution — orders may not be loaded at import time.
