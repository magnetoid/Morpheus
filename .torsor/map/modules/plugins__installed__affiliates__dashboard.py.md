---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/affiliates/dashboard.py

Symbols in `plugins/installed/affiliates/dashboard.py`.

- L18 `_trail(*items)` (function) — Build a breadcrumb trail with Dashboard / Affiliates / <leaf> shape.
- L29 `_affiliate_commission_override(affiliate)` (function) — Per-affiliate override percent (stored as Metafield). Empty string when unset.
- L49 `_affiliate_apply_status(aff, action)` (function) — Mutate + save an Affiliate based on a status action. Returns True on hit.
- L72 `_affiliates_handle_post(request)` (function)
- L100 `affiliates_list(request)` (function) — List of affiliates ordered by lifetime payout, with bulk + per-row actions.
- L138 `_payouts_csv_response(qs)` (function)
- L175 `_payouts_bulk_mark_paid(request)` (function)
- L194 `_payouts_single_action(p, action)` (function)
- L215 `_payouts_handle_post(request)` (function)
- L236 `payouts_list(request)` (function)
- L271 `programs_list(request)` (function) — Manage AffiliateProgram rows — commission tiers.
- L342 `_links_csv_response(qs)` (function)
- L380 `links_list(request)` (function) — Top affiliate links by clicks / conversions, filterable + CSV export.
- L429 `_conversions_csv_response(qs)` (function)
- L463 `conversions_list(request)` (function) — Attributed orders — which affiliate earned which conversion.
- L515 `analytics(request)` (function) — KPI summary + trend table + top performers.
- L637 `affiliate_detail(request, affiliate_id)` (function) — Per-affiliate drill-in: 30d KPIs + top links + recent conversions + edit form.
- L734 `_parse_tiers(raw: str)` (function) — Parse + sanitise the tiers JSON textarea. Returns a clean list of
- L763 `_parse_category_overrides(raw: str)` (function) — Parse + sanitise the per-category overrides JSON textarea. Returns a
- L787 `_program_options_from_post(request)` (function) — Extract the advanced OPTIONS (tiers, category overrides, auto-approve)
- L811 `_program_stats(program)` (function) — 30-day KPIs + top-10 affiliates for a program. ``(stats, top)``.
- L858 `_save_program(request, program, *, is_new)` (function) — Create or update an AffiliateProgram from POST. Returns an
- L928 `program_detail(request, program_id)` (function) — Per-program drill-in + edit form. `program_id is None` ⇒ create mode.
