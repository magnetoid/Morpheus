---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/storefront/views/content.py

Symbols in `plugins/installed/storefront/views/content.py`.

- L31 `favicon(request)` (function) — Serve the merchant's favicon when they've uploaded one.
- L55 `about(request)` (function)
- L83 `contact(request)` (function)
- L135 `journal_index(request)` (function) — The store's journal: its published CMS pages (metadata.category=='journal').
- L191 `journal_detail(request, slug)` (function)
- L242 `_amp_images(body: str)` (function) — Every <img> in a post body as a valid, closed amp-img.
- L267 `journal_amp(request, slug)` (function) — AMP variant of `journal_detail`. Mirrors the regular view's context
- L308 `_policy_page(slug: str)` (function) — The merchant's own published CMS page for a policy route, if there is one.
- L320 `_policy(request, *, slug: str, template: str, title: str, description: str)` (function) — A policy page: the merchant's CMS page when one exists, else the theme's.
- L359 `shipping(request)` (function) — Shipping policy — the merchant's CMS page, else the theme's.
- L374 `returns(request)` (function) — Returns policy — the merchant's CMS page, else the theme's.
- L388 `do_not_sell(request)` (function) — CCPA "Do not sell my info" opt-out page.
- L454 `affiliate_terms(request)` (function) — The affiliate programme's terms — only while there is a programme.
- L471 `coming_soon(request, slug=None)` (function) — Generic placeholder for footer links that don't have first-class pages yet.
