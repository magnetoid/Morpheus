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

# plugins/installed/affiliates/dashboard.py

Symbols in `plugins/installed/affiliates/dashboard.py`.

- L21 `_trail(*items)` (function)
- L25 `_affiliate_commission_override(affiliate)` (function) — Per-affiliate override percent (stored as Metafield). Empty string when unset.
- L45 `_send_affiliate_approved(aff)` (function) — Email an affiliate that they've been approved (central email registry).
- L71 `_affiliate_apply_status(aff, action)` (function) — Mutate + save an Affiliate based on a status action. Returns True on hit.
- L97 `_affiliates_handle_post(request)` (function)
- L126 `affiliates_list(request)` (function) — List of affiliates ordered by lifetime payout, with bulk + per-row actions.
- L164 `_payouts_csv_response(qs)` (function)
- L201 `_payouts_bulk_mark_paid(request)` (function)
- L220 `_payouts_single_action(p, action)` (function)
- L241 `_payouts_handle_post(request)` (function)
- L263 `payouts_list(request)` (function)
- L299 `programs_list(request)` (function) — Manage AffiliateProgram rows — commission tiers.
- L377 `_links_csv_response(qs)` (function)
- L416 `links_list(request)` (function) — Top affiliate links by clicks / conversions, filterable + CSV export.
- L465 `_conversions_csv_response(qs)` (function)
- L500 `conversions_list(request)` (function) — Attributed orders — which affiliate earned which conversion.
- L553 `analytics(request)` (function) — KPI summary + trend table + top performers.
- L676 `affiliate_detail(request, affiliate_id)` (function) — Per-affiliate drill-in: 30d KPIs + top links + recent conversions + edit form.
- L773 `_parse_tiers(raw: str)` (function) — Parse + sanitise the tiers JSON textarea. Returns a clean list of
- L802 `_parse_category_overrides(raw: str)` (function) — Parse + sanitise the per-category overrides JSON textarea. Returns a
- L826 `_program_options_from_post(request)` (function) — Extract the advanced OPTIONS (tiers, category overrides, auto-approve)
- L850 `_program_stats(program)` (function) — 30-day KPIs + top-10 affiliates for a program. ``(stats, top)``.
- L897 `_save_program(request, program, *, is_new)` (function) — Create or update an AffiliateProgram from POST. Returns an
- L974 `program_detail(request, program_id)` (function) — Per-program drill-in + edit form. `program_id is None` ⇒ create mode.
- L1023 `creatives_list(request)` (function) — Merchant management of affiliate marketing creatives — upload images +
