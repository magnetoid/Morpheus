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

# core/tests/test_rollback_notice.py

Symbols in `core/tests/test_rollback_notice.py`.

- L23 `VersionTests` (class)
- L24 `test_versions_compare_as_numbers(self)` (method)
- L30 `test_an_unparsable_version_is_never_older(self)` (method)
- L37 `RecordTests` (class)
- L38 `test_an_older_version_after_a_newer_deploy_is_a_rollback(self)` (method)
- L44 `test_a_newer_version_is_not_a_rollback(self)` (method)
- L49 `test_the_marker_names_the_row_this_container_wrote(self)` (method)
- L54 `test_the_failed_release_s_backup_is_found_by_its_version(self)` (method)
- L61 `test_the_backup_named_is_the_first_one_that_release_took(self)` (method)
- L73 `SafeMigrateOrderTests` (class)
- L74 `_run(self, migrate=None, record=None, alert=None)` (method)
- L91 `test_the_attempt_is_recorded_before_migrating(self)` (method)
- L103 `test_a_restart_after_a_crashed_migration_adds_no_row(self)` (method)
- L114 `test_a_record_that_cannot_be_written_yet_is_written_after_migrating(self)` (method)
- L129 `test_the_operators_hear_once(self)` (method)
- L144 `test_the_operators_hear_once_the_store_has_migrated(self)` (method)
- L156 `test_an_email_that_fails_does_not_stop_the_boot(self)` (method)
- L170 `RollbackEmailTests` (class)
- L171 `test_the_email_gives_up_on_a_mail_server_that_does_not_answer(self)` (method)
- L181 `FailedBackupTests` (class)
- L182 `_fail(self)` (method)
- L191 `test_a_failed_backup_leaves_the_attempt_for_the_rollback_notice(self)` (method)
- L204 `RunningReleaseTests` (class)
- L205 `test_the_page_names_the_rollback_and_the_failed_backup(self)` (method)
- L215 `test_the_card_says_the_store_was_put_back(self)` (method)
