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

# core/tests/test_safe_migrate.py

Symbols in `core/tests/test_safe_migrate.py`.

- L36 `_fake_dump(self, workdir)` (function)
- L42 `_broken_dump(self, workdir)` (function)
- L46 `_DeployEnvMixin` (class) — A temporary backup folder and marker file, and a known commit.
- L49 `setUp(self)` (method)
- L62 `pend(self)` (method) — Mark core's newest migration unapplied, so `migrate` would run it.
- L71 `archives(self)` (method)
- L75 `MigrationPlanTests` (class)
- L76 `test_a_migrated_database_has_nothing_pending(self)` (method)
- L79 `test_an_unapplied_migration_is_pending(self)` (method)
- L84 `SafeMigrateTests` (class)
- L85 `run_command(self, dump=_fake_dump, migrate=None)` (method)
- L94 `test_nothing_to_migrate_takes_no_backup(self)` (method)
- L100 `test_the_database_is_backed_up_before_migrating(self)` (method)
- L116 `test_the_last_five_are_kept_and_the_nightly_ones_untouched(self)` (method)
- L131 `test_a_failed_backup_stops_before_migrating_and_leaves_nothing(self)` (method)
- L144 `test_a_restart_after_a_failed_migrate_does_not_back_up_again(self)` (method)
- L161 `test_a_new_database_has_nothing_to_back_up(self)` (method)
- L171 `test_a_successful_run_clears_the_marker(self)` (method)
- L176 `test_migrate_runs_its_system_checks_without_prompts(self)` (method)
- L184 `BackupArchiveTests` (class)
- L185 `backup(self, **options)` (method)
- L193 `test_a_backup_that_fails_while_writing_leaves_no_archive(self)` (method)
- L201 `test_a_backup_being_written_never_has_a_finished_backups_name(self)` (method)
- L217 `test_the_next_backup_removes_a_killed_backups_leftover(self)` (method)
- L227 `test_a_label_is_made_safe_for_a_file_name(self)` (method)
- L231 `test_no_label_keeps_the_nightly_name(self)` (method)
- L236 `DeployWiringTests` (class)
- L237 `test_the_web_container_keeps_its_backups_on_the_backup_volume(self)` (method)
- L243 `boot(self, exit_code)` (method) — The entrypoint's web mode, with stand-in `python` and `gunicorn`.
- L262 `test_migrations_go_through_safe_migrate_before_gunicorn(self)` (method)
- L268 `test_a_failed_backup_stops_the_boot(self)` (method)
