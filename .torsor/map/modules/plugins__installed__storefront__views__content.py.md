---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/storefront/views/content.py

Symbols in `plugins/installed/storefront/views/content.py`.

- L58 `about(request)` (function)
- L75 `newsletter_subscribe(request)` (function) — Capture a footer newsletter signup as a CRM Lead.
- L112 `contact(request)` (function)
- L157 `journal_index(request)` (function) — Prefer CMS pages (metadata.category=='journal'); fall back to seeded entries.
- L193 `journal_detail(request, slug)` (function)
- L233 `journal_amp(request, slug)` (function) — AMP variant of `journal_detail`. Mirrors the regular view's context
- L285 `shipping(request)` (function) — Real shipping policy page.
- L302 `returns(request)` (function) — Real returns policy page.
- L319 `do_not_sell(request)` (function) — CCPA "Do not sell my info" opt-out page.
- L378 `coming_soon(request, slug=None)` (function) — Generic placeholder for footer links that don't have first-class pages yet.
