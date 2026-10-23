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

# plugins/installed/seo/tests/test_audit_fixes_2026_09.py

Symbols in `plugins/installed/seo/tests/test_audit_fixes_2026_09.py`.

- L17 `XDefaultTests` (class) — `x-default` names the default language, not whichever page you are on.
- L20 `_alternates(self, path: str)` (method)
- L34 `test_both_language_trees_name_the_same_x_default(self)` (method)
- L46 `test_single_language_store_emits_no_alternates(self)` (method)
- L50 `XDefaultSelectionTests` (class) — `_x_default_href` in isolation — no request plumbing.
- L53 `_pick(self, languages, canonical='https://x.test/here/', code='en')` (method)
- L59 `test_picks_the_default_language(self)` (method)
- L63 `test_regional_language_code_falls_back_to_the_base_tag(self)` (method)
- L67 `test_market_only_store_keeps_the_canonical(self)` (method)
- L72 `LlmsTxtTests` (class)
- L73 `_render(self, **kwargs)` (method)
- L78 `test_no_double_slashes_in_urls(self)` (method)
- L83 `test_no_empty_products_heading(self)` (method)
- L89 `test_site_map_does_not_link_a_redirecting_route(self)` (method)
- L93 `test_owners_contribute_their_own_sections(self)` (method)
- L110 `test_a_broken_subscriber_does_not_take_the_file_down(self)` (method)
- L123 `JournalGraphTests` (class) — What the journal page actually publishes is the GRAPH, not the tags.
- L133 `_graph(self, *, body: str, metadata: dict | None=None)` (method)
- L155 `_node(self, graph, node_type)` (method)
- L158 `test_author_same_as_and_citations_reach_the_graph(self)` (method)
- L172 `test_question_headings_publish_an_faqpage_node(self)` (method)
- L190 `test_an_article_without_questions_publishes_no_faqpage(self)` (method)
- L195 `ErrorPageRobotsTests` (class) — A 404 must not ask to be indexed.
- L205 `test_404_resolves_as_private(self)` (method)
- L213 `test_the_error_page_is_named_for_a_human(self)` (method)
- L224 `test_an_ordinary_page_is_untouched(self)` (method)
- L232 `test_the_rendered_404_carries_exactly_one_noindex(self)` (method)
