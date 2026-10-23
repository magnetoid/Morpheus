---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/janus/tests/test_janus.py

Symbols in `plugins/installed/janus/tests/test_janus.py`.

- L42 `_set(**config)` (function)
- L46 `_stored()` (function)
- L51 `JanusPageBoundaryTests` (class)
- L52 `setUp(self)` (method)
- L61 `test_anonymous_blocked(self)` (method)
- L66 `test_authed_without_staff_blocked(self)` (method)
- L70 `test_staff_allowed(self)` (method)
- L77 `JanusPageSaveTests` (class)
- L78 `setUp(self)` (method)
- L85 `_post(self, **overrides)` (method)
- L88 `test_backup_providers_are_saved_in_order_and_shown(self)` (method)
- L96 `test_an_unknown_backup_provider_is_refused(self)` (method)
- L100 `test_save_persists_every_field(self)` (method)
- L120 `test_limits_are_enforced(self)` (method)
- L125 `test_the_new_upper_limits_can_be_saved(self)` (method)
- L130 `test_pinned_provider_needs_provider_model_and_key(self)` (method)
- L136 `test_api_key_is_write_only(self)` (method)
- L151 `test_saved_key_can_be_removed(self)` (method)
- L161 `test_an_unpriced_custom_model_is_refused(self)` (method)
- L174 `test_base_url_must_be_http(self)` (method)
- L178 `test_change_is_audited_without_values(self)` (method)
- L192 `test_connection_test_reports_the_engine_result(self)` (method)
- L199 `test_page_url_is_not_shadowed_by_the_settings_deep_link(self)` (method)
- L208 `test_page_is_listed_under_settings_ai(self)` (method)
- L214 `test_app_cannot_be_switched_off(self)` (method)
- L220 `JanusSettingConsumerTests` (class) — Each stored setting changes what the engine or the turn actually does.
- L223 `setUp(self)` (method)
- L226 `test_switched_off_linda_declines_without_starting_the_engine(self)` (method)
- L234 `test_standing_instructions_reach_the_prompt(self)` (method)
- L239 `test_tool_step_cap_reaches_the_engine_config(self)` (method)
- L243 `test_tool_step_cap_is_clamped(self)` (method)
- L249 `test_bundled_skills_toggle_reaches_the_engine_config(self)` (method)
- L253 `test_thinking_effort_reaches_the_engine_config(self)` (method)
- L260 `test_web_search_toggle_reaches_the_engine_and_the_prompt(self)` (method)
- L266 `test_learning_toggle_reaches_the_engine(self)` (method)
- L272 `test_unset_time_limit_is_four_minutes(self)` (method)
- L277 `test_time_limit_reaches_the_engine(self)` (method)
- L281 `test_time_limit_never_exceeds_the_worker_timeout(self)` (method)
- L285 `test_pinned_provider_reaches_the_engine(self)` (method)
- L291 `test_incomplete_pin_falls_back_to_the_store_provider(self)` (method)
- L295 `test_unknown_provider_is_never_pinned(self)` (method)
- L300 `JanusLearningReviewTests` (class) — The merchant can see and delete everything Linda learned.
- L303 `setUp(self)` (method)
- L337 `test_page_lists_what_linda_learned(self)` (method)
- L345 `test_notes_about_a_colleague_are_not_shown(self)` (method)
- L348 `test_deleting_a_note_removes_only_that_note_and_is_audited(self)` (method)
- L360 `test_a_colleagues_note_cannot_be_deleted_from_here(self)` (method)
- L371 `test_deleting_a_skill_and_lessons(self)` (method)
- L377 `test_an_unknown_skill_path_deletes_nothing(self)` (method)
