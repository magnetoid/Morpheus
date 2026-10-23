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

# core/assistant/tests/test_janus_updates.py

Symbols in `core/assistant/tests/test_janus_updates.py`.

- L28 `_venv(root: Path, sha: str, *, marker: dict | None=None, url: str | None=None)` (function) — A fake Janus venv: bin/janus plus the dist-info pip would write.
- L51 `_github(sha=NEW, title='feat: faster tools')` (function)
- L59 `InstalledBuildTests` (class)
- L60 `setUp(self)` (method)
- L65 `test_the_image_build_is_read_from_pips_git_record(self)` (method)
- L72 `test_an_auto_installed_build_is_read_from_the_archive_url_and_marker(self)` (method)
- L82 `_EngineDirMixin` (class)
- L83 `setUp(self)` (method)
- L92 `_activate(self, sha=NEW, *, previous=None, failures=0)` (method)
- L103 `ActiveBinTests` (class)
- L104 `test_a_verified_auto_install_is_used(self)` (method)
- L108 `test_nothing_installed_means_the_image_janus(self)` (method)
- L111 `test_a_venv_without_its_verification_marker_is_ignored(self)` (method)
- L116 `test_a_path_outside_the_engine_dir_is_ignored(self)` (method)
- L126 `test_the_deployment_switch_turns_it_off(self)` (method)
- L130 `test_the_merchant_switch_turns_it_off(self)` (method)
- L139 `test_the_engine_runs_the_auto_installed_janus(self)` (method)
- L146 `test_an_explicit_janus_bin_still_wins(self)` (method)
- L155 `MaybeUpdateTests` (class)
- L156 `_source(self, ref='main')` (method)
- L163 `test_a_due_check_starts_the_updater_in_the_background(self)` (method)
- L177 `test_checks_are_spaced_out(self)` (method)
- L185 `test_a_build_pinned_to_a_commit_is_never_auto_updated(self)` (method)
- L206 `test_the_image_branch_is_the_update_source(self)` (method)
- L213 `test_a_failure_to_start_never_reaches_the_turn(self)` (method)
- L219 `RollbackTests` (class)
- L220 `_state(self)` (method)
- L223 `test_three_engine_failures_in_a_row_put_the_previous_janus_back(self)` (method)
- L233 `test_a_success_resets_the_count(self)` (method)
- L241 `test_provider_trouble_and_timeouts_say_nothing_about_the_build(self)` (method)
- L252 `test_an_engine_failure_that_mentions_generating_still_counts(self)` (method)
- L260 `test_the_image_janus_is_never_rolled_back(self)` (method)
- L265 `UpdaterTests` (class) — The detached updater, with GitHub and pip faked.
- L268 `setUp(self)` (method)
- L273 `_args(self, **kw)` (method)
- L285 `_fake_tools(self, contract_ok=True, pip_rc=0)` (method)
- L309 `_state(self)` (method)
- L312 `test_nothing_newer_installs_nothing(self)` (method)
- L318 `test_a_newer_commit_that_keeps_the_contract_becomes_the_janus_to_use(self)` (method)
- L336 `test_a_commit_that_breaks_the_contract_is_never_used(self)` (method)
- L345 `test_a_failed_install_is_recorded_and_cleaned_up(self)` (method)
- L352 `test_a_failed_commit_is_not_retried_until_forced(self)` (method)
- L360 `test_github_trouble_is_recorded_not_raised(self)` (method)
- L365 `test_the_replaced_janus_is_kept_for_a_rollback_and_older_ones_go(self)` (method)
- L381 `test_one_update_at_a_time(self)` (method)
- L404 `test_arguments_are_validated_before_anything_is_fetched(self)` (method)
- L412 `test_it_runs_without_django(self)` (method)
- L418 `DockerfileTests` (class) — The image and the updater install Janus the same way, and both check it.
- L421 `test_the_build_checks_janus_and_pins_what_the_updater_installs(self)` (method)
