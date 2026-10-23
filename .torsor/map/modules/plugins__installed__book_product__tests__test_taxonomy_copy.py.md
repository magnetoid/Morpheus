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

# plugins/installed/book_product/tests/test_taxonomy_copy.py

Symbols in `plugins/installed/book_product/tests/test_taxonomy_copy.py`.

- L32 `_staff_client(username: str)` (function)
- L41 `RootTaxonomyChoicesTests` (class)
- L42 `test_curated_kinds_can_have_a_root_but_not_a_term(self)` (method) — Genre/Topic index pages need a root row; their TERMS carry their own
- L50 `test_every_term_kind_is_also_a_root_kind(self)` (method)
- L53 `test_genre_root_row_is_storable(self)` (method)
- L59 `CuratedRootRendersIntroTests` (class) — The storefront /genres/ + /topics/ pages must render their intro.
- L62 `setUp(self)` (method)
- L74 `test_genres_index_renders_root_description(self)` (method)
- L86 `test_topics_index_renders_root_description(self)` (method)
- L92 `test_index_without_a_root_still_renders(self)` (method)
- L98 `CuratedRootDashboardTests` (class)
- L99 `setUp(self)` (method)
- L103 `test_landing_editor_saves_a_genre_root(self)` (method)
- L111 `test_taxonomies_list_offers_a_landing_editor_for_curated_kinds(self)` (method)
- L122 `test_unknown_root_kind_is_rejected(self)` (method)
- L130 `BulkCopyBackfillTests` (class) — The backfill writes the pages that matter and never clobbers hand copy.
- L133 `setUp(self)` (method)
- L151 `_fake_copy(self, *args, **kwargs)` (method)
- L158 `test_writes_only_stocked_terms_missing_copy(self)` (method)
- L173 `test_never_overwrites_existing_copy(self)` (method)
- L187 `test_limit_is_capped_and_honoured(self)` (method)
- L197 `test_provider_failure_skips_the_row_not_the_batch(self)` (method)
- L214 `test_unknown_kind_is_a_no_op(self)` (method)
- L220 `BackfillCountHonestyTests` (class) — The button's number and the task's target set must be the SAME set.
- L230 `setUp(self)` (method)
- L247 `test_count_matches_what_the_task_targets(self)` (method)
- L255 `test_draft_only_genre_is_not_advertised(self)` (method)
- L263 `BackfillLockTests` (class) — Every term is a paid LLM call, so a re-click must not queue a second run.
- L266 `setUp(self)` (method)
- L278 `test_second_click_while_running_does_not_queue_again(self)` (method)
- L285 `test_lock_is_released_when_the_run_finishes(self)` (method)
- L306 `CopyServiceTests` (class)
- L307 `test_prompt_is_grounded_in_the_actual_books(self)` (method)
- L320 `test_unknown_taxonomy_raises(self)` (method)
- L327 `MalformedResponseTests` (class) — Junk must never reach a storefront page.
- L334 `setUp(self)` (method)
- L342 `_generate_returning(self, raw)` (method)
- L349 `test_truncated_json_raises_instead_of_publishing_it(self)` (method)
- L355 `test_broken_json_raises(self)` (method)
- L361 `test_a_terse_answer_is_returned_to_the_human(self)` (method) — The length guard lives in the AUTO-PUBLISH path, not here: the
- L369 `test_backfill_refuses_to_publish_a_too_short_answer(self)` (method)
- L379 `test_plain_prose_is_still_accepted(self)` (method) — A model that ignores the JSON instruction but writes real copy is
- L385 `test_backfill_skips_a_malformed_row(self)` (method)
