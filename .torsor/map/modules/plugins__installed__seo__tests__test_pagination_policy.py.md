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

# plugins/installed/seo/tests/test_pagination_policy.py

Symbols in `plugins/installed/seo/tests/test_pagination_policy.py`.

- L30 `_FakePage` (class)
- L31 `__init__(self, number)` (method)
- L35 `PageOneRedirectTests` (class) — A listing and that listing `?page=1` are one page under two names.
- L38 `setUp(self)` (method)
- L41 `test_page_one_is_redirected_away(self)` (method)
- L46 `test_the_rest_of_the_query_survives_the_redirect(self)` (method) — Dropping a campaign tag on the way through would break attribution
- L55 `test_a_real_page_number_is_left_alone(self)` (method)
- L58 `test_every_spelling_of_page_one_collapses(self)` (method) — A paginator reads `int(value)`; `?page=01` is page 1 wearing a hat.
- L65 `test_a_page_value_that_is_not_a_number_is_left_for_the_view(self)` (method) — Redirecting it would hide the 404 the view is right to return.
- L69 `test_a_url_with_no_page_parameter_is_left_alone(self)` (method)
- L72 `test_a_post_is_never_redirected(self)` (method) — A 301 would turn a form submission into a GET and lose the body.
- L79 `OutOfRangePageTests` (class) — A page that is not there gets the same answer as any other URL that is
- L84 `setUpTestData(cls)` (method)
- L94 `test_a_page_past_the_end_is_a_404(self)` (method)
- L97 `test_a_page_number_that_is_not_a_number_is_a_404(self)` (method)
- L100 `test_the_first_page_still_renders(self)` (method)
- L103 `test_an_empty_listing_still_renders(self)` (method) — Page 1 of nothing is a page — an empty category must not 404.
- L108 `test_an_out_of_range_page_is_not_logged_as_a_broken_url(self)` (method) — The 404 log records `path_info` with the query stripped, so this 404
- L118 `test_a_genuinely_missing_url_is_still_logged(self)` (method)
- L124 `test_a_category_page_past_the_end_is_a_404_too(self)` (method)
- L132 `RenderedPageTwoTests` (class) — The whole chain, on a real second page.
- L143 `setUpTestData(cls)` (method)
- L157 `_head(self, url: str)` (method)
- L161 `_canonical(self, url: str)` (method)
- L165 `test_page_two_is_canonical_to_itself(self)` (method)
- L168 `test_page_two_carries_its_own_title(self)` (method)
- L171 `test_page_two_is_still_indexable(self)` (method)
- L174 `test_page_one_is_canonical_to_the_clean_url(self)` (method) — `rel=next` still names page 2 — it is the canonical that must not.
- L178 `test_rel_prev_from_page_two_names_the_clean_url(self)` (method) — Not `?page=1`, which we would immediately 301 — a wasted hop for
- L187 `PaginatedTitleTests` (class) — Every page of a listing otherwise carries the category's title, so an
- L191 `test_page_two_gets_its_own_title(self)` (method)
- L194 `test_page_one_is_the_category(self)` (method)
- L197 `test_no_paginator_changes_nothing(self)` (method)
- L201 `_request(url: str)` (function)
