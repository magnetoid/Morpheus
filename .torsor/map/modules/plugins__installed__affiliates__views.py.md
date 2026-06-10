---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/affiliates/views.py

Symbols in `plugins/installed/affiliates/views.py`.

- L30 `affiliate_redirect(request: HttpRequest, code: str)` (function)
- L71 `apply(request: HttpRequest)` (function) — Affiliate application form. Creates a `pending` Affiliate row that an
- L148 `_affiliate_or_redirect(request)` (function) — Return ``(affiliate, redirect_response)``. Exactly one is non-None.
- L173 `dashboard(request: HttpRequest)` (function) — Affiliate dashboard overview.
- L292 `create_link(request: HttpRequest)` (function) — Create a tracked affiliate link from the dashboard's inline form.
- L321 `links(request: HttpRequest)` (function) — Full inventory of an affiliate's tracked links + search/filter.
- L359 `edit_link(request: HttpRequest, link_id)` (function) — Inline edit: label + active toggle.
- L387 `conversions(request: HttpRequest)` (function) — Conversion log + optional CSV export.
- L444 `_min_payout_threshold(affiliate)` (function) — Read the program's minimum_payout, falling back to $25.
- L459 `payouts(request: HttpRequest)` (function) — Pending earnings card + request-payout form + past payouts table.
- L516 `_widget_categories()` (function) — Active categories for the widget create form's category picker.
- L523 `_resolve_product_ids(raw: str)` (function) — Map a comma/newline list of product slugs to active product UUIDs.
- L539 `_apply_widget_form(widget, request)` (function) — Mutate ``widget`` in place from POST data (shared by create + edit).
- L573 `widgets(request: HttpRequest)` (function) — Affiliate-owned embeddable widgets: list + create + copy embed codes.
- L614 `edit_widget(request: HttpRequest, widget_id)` (function) — Update / toggle / delete an owned widget. Owner-scoped: the queryset is
- L645 `settings(request: HttpRequest)` (function) — Editable affiliate profile: display name, payout email, method, bio.
