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

# plugins/installed/booking_marketplace/tests/test_search_engine.py

Symbols in `plugins/installed/booking_marketplace/tests/test_search_engine.py`.

- L16 `_doc(key, name, *, location='', region='', description='', kind='experience')` (function)
- L55 `_find(q, kind='experience', **kwargs)` (function)
- L59 `_ranked(q, **kwargs)` (function)
- L64 `FoldTests` (class)
- L65 `test_accents_case_and_cyrillic_fold_to_one_word(self)` (method)
- L72 `test_a_word_with_dj_is_indexed_both_ways(self)` (method)
- L75 `test_one_edit(self)` (method)
- L89 `QueryTests` (class)
- L90 `test_stopwords_and_repeats_are_dropped(self)` (method)
- L94 `test_store_wide_words_are_stopwords(self)` (method)
- L98 `test_a_long_query_is_capped(self)` (method)
- L103 `test_synonyms_and_singulars_are_variants(self)` (method)
- L110 `MatchingTests` (class)
- L111 `test_every_word_must_match_in_any_order(self)` (method)
- L115 `test_a_name_match_ranks_above_a_description_match(self)` (method)
- L120 `test_accents_and_cyrillic(self)` (method)
- L125 `test_dj_is_read_both_ways(self)` (method)
- L130 `test_a_serbian_word_finds_the_english_listing(self)` (method)
- L133 `test_a_typo_and_a_prefix(self)` (method)
- L137 `test_a_word_that_matches_is_not_read_as_a_typo(self)` (method)
- L141 `test_close_matches_when_no_listing_has_every_word(self)` (method)
- L146 `test_no_close_matches_without_the_fallback(self)` (method)
- L149 `test_nothing_to_search_for(self)` (method)
- L153 `test_kind_and_within_restrict_the_keys(self)` (method)
- L160 `test_a_possessive_is_one_word(self)` (method)
