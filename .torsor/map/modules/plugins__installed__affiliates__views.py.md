---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/affiliates/views.py

Symbols in `plugins/installed/affiliates/views.py`.

- L34 `affiliate_redirect(request: HttpRequest, code: str)` (function)
- L84 `program_page(request: HttpRequest)` (function) — The public affiliate program page: what each open program pays, how it
- L128 `apply(request: HttpRequest)` (function) — Affiliate application form. Creates a `pending` Affiliate row that an
- L223 `_affiliate_or_redirect(request)` (function) — Return ``(affiliate, redirect_response)``. Exactly one is non-None.
- L248 `_shell(affiliate, active: str, title: str, **extra)` (function)
- L257 `_site_base(request)` (function)
- L261 `_highlighted_link(request, affiliate)` (function) — The link named by ``?new=<code>`` — the one the builder just made.
- L271 `_product_choices(limit: int=300)` (function) — Active products for the link builder's suggestions: name → page path.
- L281 `dashboard(request: HttpRequest)` (function) — The affiliate's overview: period KPIs against the period before, the
- L344 `create_link(request: HttpRequest)` (function) — The link builder: turn a page of the store into a tracked link.
- L400 `links(request: HttpRequest)` (function) — The link builder and every tracked link, with what each one earned.
- L457 `edit_link(request: HttpRequest, link_id)` (function) — Inline edit: label + active toggle.
- L486 `_filter_orders(qs, status: str)` (function) — Filter conversions by where their commission stands. "Paid" includes an
- L502 `conversions(request: HttpRequest)` (function) — Every referred order, filterable by where its commission stands, + CSV export.
- L569 `payouts(request: HttpRequest)` (function) — Balance, progress to the minimum payout, the request form and the history.
- L627 `_widget_categories()` (function) — Active categories for the widget create form's category picker.
- L634 `_resolve_product_ids(raw: str)` (function) — Map a comma/newline list of product slugs to active product UUIDs.
- L650 `_apply_widget_form(widget, request)` (function) — Mutate ``widget`` in place from POST data (shared by create + edit).
- L684 `widgets(request: HttpRequest)` (function) — Affiliate-owned embeddable widgets: list + create + copy embed codes.
- L728 `edit_widget(request: HttpRequest, widget_id)` (function) — Update / toggle / delete an owned widget. Owner-scoped: the queryset is
- L759 `settings(request: HttpRequest)` (function) — Editable affiliate profile: display name, payout email, method, bio.
- L816 `leaderboard(request: HttpRequest)` (function) — Top affiliates by sales driven — a motivational leaderboard. Shows
- L870 `creatives(request: HttpRequest)` (function) — Affiliate-facing marketing creatives library — grab a banner/cover +
- L894 `analytics(request: HttpRequest)` (function) — The affiliate's own performance over 7, 30 or 90 days: clicks per day,
- L949 `coupon(request: HttpRequest)` (function) — The affiliate's personal coupon code — claim a handle-derived code, then
