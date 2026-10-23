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

# plugins/installed/affiliates/tests/test_portal.py

Symbols in `plugins/installed/affiliates/tests/test_portal.py`.

- L52 `_portal(body: str)` (function) — The portal's own markup — the theme around it has its own copy.
- L58 `_portal_words(body: str)` (function) — The portal's own wording: its markup without the store's data (category
- L64 `_Base` (class)
- L65 `setUp(self)` (method)
- L85 `_conversion(self, *, commission, status='approved', days_ago=0, affiliate=None, link=None)` (method)
- L106 `_clicks(self, n, *, days_ago=0, link=None)` (method)
- L116 `PortalShellTests` (class)
- L117 `test_every_page_renders_in_the_shell_with_its_tab_current(self)` (method)
- L128 `test_each_page_has_one_robots_tag_and_it_says_noindex(self)` (method)
- L137 `test_no_page_speaks_a_bookshop(self)` (method)
- L143 `test_a_pending_affiliate_sees_the_application_not_the_tabs(self)` (method)
- L150 `test_someone_without_an_account_is_invited_to_apply(self)` (method)
- L160 `NumbersTests` (class)
- L161 `test_kpis_compare_the_period_with_the_one_before(self)` (method)
- L171 `test_earnings_come_from_the_conversions_not_the_balance_column(self)` (method)
- L182 `test_commission_in_review_is_counted_apart(self)` (method)
- L188 `test_the_cookie_window_is_the_programs(self)` (method)
- L192 `test_what_customers_bought_comes_from_the_referred_orders(self)` (method)
- L204 `test_another_affiliates_activity_never_shows(self)` (method)
- L223 `test_conversions_filter_paid_includes_a_paid_payout(self)` (method)
- L235 `CopyTests` (class)
- L236 `test_no_promise_the_store_does_not_keep(self)` (method)
- L243 `test_store_credit_is_not_labelled_with_a_bonus(self)` (method)
- L247 `LinkBuilderTests` (class)
- L248 `_create(self, url, label='', **extra)` (method)
- L253 `test_a_page_of_this_store_becomes_a_tracked_link(self)` (method)
- L262 `test_another_site_is_refused(self)` (method)
- L275 `test_the_same_untitled_link_is_not_made_twice(self)` (method)
- L280 `test_a_malformed_affiliate_id_does_not_crash(self)` (method)
- L285 `test_someone_elses_affiliate_id_makes_no_link_for_them(self)` (method)
- L295 `test_the_redirect_never_leaves_the_store(self)` (method)
- L305 `test_the_redirect_keeps_a_store_page(self)` (method)
- L312 `StorePathTests` (class)
- L313 `test_accepts_paths_and_own_host_urls(self)` (method)
- L322 `test_refuses_anything_else(self)` (method)
