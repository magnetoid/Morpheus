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

# plugins/installed/book_product/tests/test_listing_facets.py

Symbols in `plugins/installed/book_product/tests/test_listing_facets.py`.

- L27 `_book(slug, *, author='', pages=None, genres=(), topics=(), variants=())` (function)
- L50 `_q(query: str)` (function)
- L54 `_facet(facets, key)` (function)
- L58 `_counts(facet)` (function)
- L62 `FacetFixture` (class)
- L64 `setUpTestData(cls)` (method)
- L95 `base(self)` (method)
- L99 `SelectionTests` (class)
- L100 `test_repeated_keys_become_lists_without_blanks_or_repeats(self)` (method)
- L108 `ApplyTests` (class)
- L109 `_slugs(self, query)` (method)
- L112 `test_values_inside_a_facet_widen(self)` (method)
- L117 `test_facets_narrow_each_other(self)` (method)
- L120 `test_author_matches_ignoring_case(self)` (method)
- L123 `test_length_buckets_and_books_without_a_page_count(self)` (method)
- L130 `test_format_rules(self)` (method)
- L135 `test_an_unknown_value_narrows_to_nothing_not_everything(self)` (method)
- L138 `test_an_unknown_format_or_length_is_ignored(self)` (method)
- L143 `DescribeTests` (class)
- L144 `test_counts_ignore_the_facets_own_choice(self)` (method)
- L150 `test_a_choice_that_leaves_nothing_is_hidden_unless_selected(self)` (method)
- L159 `test_a_topic_with_one_book_is_not_listed(self)` (method)
- L163 `test_a_selected_author_typed_in_another_case_is_shown_selected(self)` (method)
- L168 `test_order_labels_and_search(self)` (method)
- L185 `AnswerTests` (class)
- L186 `test_the_hook_answer_narrows_and_describes(self)` (method)
- L196 `test_sorts_by_author_and_length(self)` (method)
