---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/tests/test_deploy_guard.py

Symbols in `core/tests/test_deploy_guard.py`.

- L36 `_Clock` (class) — A fake clock that only sleeping moves.
- L39 `__init__(self)` (method)
- L42 `__call__(self)` (method)
- L45 `sleep(self, seconds)` (method)
- L49 `_get(responses)` (function) — A fake GET: each URL answers from its list, one entry per call, the last repeating.
- L62 `VersionTests` (class)
- L63 `test_the_previous_release_ignores_other_tags_and_order(self)` (method)
- L68 `test_the_version_being_deployed_is_read_from_settings(self)` (method)
- L73 `StateTests` (class)
- L74 `test_a_refusal_is_not_an_unhealthy_answer(self)` (method)
- L82 `test_ok_needs_readyz_and_the_home_page(self)` (method)
- L89 `ClassifyTests` (class)
- L90 `_classify(self, responses, stores=('https://s',))` (method)
- L97 `test_a_swap_of_two_minutes_is_not_down(self)` (method)
- L104 `test_a_store_still_on_the_old_version_is_left_alone(self)` (method)
- L108 `test_down_means_no_healthy_answer_for_the_whole_window(self)` (method)
- L113 `test_the_stores_share_one_window(self)` (method)
- L119 `test_a_store_that_refuses_the_guard_is_unknown_not_down(self)` (method)
- L123 `test_a_home_page_that_fails_is_not_up(self)` (method)
- L128 `MalformedAnswerTests` (class)
- L129 `test_a_malformed_answer_is_unhealthy_not_a_crash(self)` (method)
- L147 `_FakeCoolify` (class)
- L150 `do_POST(self)` (method)
- L161 `log_message(self, *args)` (method)
- L165 `WebhookTests` (class)
- L166 `test_the_push_is_signed_with_the_store_s_own_secret(self)` (method)
- L186 `test_an_answer_without_a_queued_deployment_is_not_success(self)` (method)
- L193 `TargetTests` (class)
- L194 `test_a_store_goes_back_to_the_release_it_served_before(self)` (method)
- L200 `test_without_a_before_version_the_previous_release_is_used(self)` (method)
- L203 `test_a_before_version_that_is_not_an_older_release_is_ignored(self)` (method)
- L207 `test_the_before_file_is_read(self)` (method)
- L218 `RollbackTests` (class)
- L227 `_run(self, after=(UP_OLD,), *, before=None, dry_run=False, contract='', post_answer=None, readyz_down=DOWN)` (method)
- L273 `test_only_the_store_that_is_down_is_put_back(self)` (method)
- L287 `test_a_store_goes_back_to_the_release_it_ran_before_this_deploy(self)` (method)
- L295 `test_going_back_past_a_contract_is_refused(self)` (method)
- L304 `test_a_dry_run_sends_nothing(self)` (method)
- L310 `test_a_webhook_that_queues_nothing_is_a_failure(self)` (method)
- L315 `test_a_store_that_stays_down_after_the_rollback_is_reported(self)` (method)
- L320 `test_a_store_that_comes_up_on_the_new_version_after_all_is_reported(self)` (method)
- L325 `test_a_store_that_refuses_the_guard_is_left_alone_and_reported(self)` (method)
- L331 `test_every_store_up_or_late_is_success(self)` (method)
- L350 `ConfigTests` (class)
- L351 `test_without_its_secret_the_guard_says_rollback_is_off(self)` (method)
- L356 `test_a_config_without_stores_is_refused(self)` (method)
- L362 `_FakeStore` (class)
- L363 `do_GET(self)` (method)
- L370 `log_message(self, *args)` (method)
- L374 `SmokeRecordsTests` (class)
- L375 `test_the_smoke_records_what_each_store_served_before(self)` (method)
- L401 `WorkflowTests` (class)
- L402 `test_deploy_smoke_runs_the_guard_when_the_smoke_fails(self)` (method)
- L410 `test_after_a_green_smoke_the_guard_checks_it_can_see_the_stores(self)` (method)
