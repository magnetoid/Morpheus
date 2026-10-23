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

# core/tests/test_morph_restore.py

Symbols in `core/tests/test_morph_restore.py`.

- L27 `_archive(folder: Path, name: str=NAME, members: dict | None=None)` (function)
- L38 `_Folder` (class)
- L39 `setUp(self)` (method)
- L49 `DescribeBackupTests` (class)
- L50 `test_a_backup_is_described_by_its_name_and_size(self)` (method)
- L57 `test_a_name_with_an_impossible_date_is_skipped(self)` (method)
- L62 `test_an_unfinished_backup_is_skipped(self)` (method)
- L68 `ExtractTests` (class)
- L69 `test_the_dump_comes_out_of_the_archive(self)` (method)
- L75 `test_an_archive_without_a_database_is_refused(self)` (method)
- L79 `test_a_file_that_is_not_an_archive_is_refused(self)` (method)
- L85 `test_a_dump_that_is_a_link_is_refused(self)` (method)
- L96 `DatabaseRestoreTests` (class)
- L99 `test_the_backup_replaces_the_whole_schema_in_one_transaction(self)` (method)
- L137 `test_a_backup_that_cannot_be_read_runs_nothing(self)` (method)
- L146 `test_a_failed_load_says_nothing_changed(self)` (method)
- L155 `test_a_sqlite_database_file_is_replaced(self)` (method)
- L165 `test_an_in_memory_database_is_refused(self)` (method)
- L171 `test_no_sessions_to_end_on_sqlite(self)` (method)
- L175 `ClearCacheTests` (class)
- L176 `test_only_the_cache_s_own_keys_go_when_redis_backs_it(self)` (method)
- L184 `test_a_cache_without_patterns_is_cleared(self)` (method)
- L191 `BackUpCurrentTests` (class)
- L192 `test_the_current_data_goes_to_its_own_folder_and_nothing_is_pruned_yet(self)` (method)
- L205 `RunTests` (class)
- L206 `setUp(self)` (method)
- L223 `_restore(self, *extra, confirm='Test Shop')` (method)
- L228 `test_the_current_data_is_saved_first_then_restored_and_recorded(self)` (method)
- L241 `test_the_wrong_name_changes_nothing_and_is_recorded(self)` (method)
- L250 `test_spaces_around_the_name_are_fine_but_case_counts(self)` (method)
- L256 `test_no_restore_while_another_runs(self)` (method)
- L264 `test_an_archive_without_a_database_never_closes_the_store(self)` (method)
- L271 `test_a_failed_restore_changes_nothing_and_says_so(self)` (method)
- L281 `test_a_failed_backup_of_the_current_data_stops_the_restore(self)` (method)
- L288 `test_cached_values_are_dropped_after_a_restore(self)` (method)
- L293 `test_a_backup_older_than_the_code_names_what_it_lacks(self)` (method)
- L300 `test_the_web_workers_reload_after_a_restore_started_from_the_page(self)` (method)
- L305 `test_nothing_reloads_after_a_failed_restore(self)` (method)
- L311 `test_the_store_is_closed_while_the_data_is_replaced(self)` (method)
- L318 `SpawnTests` (class)
- L319 `test_the_restore_runs_detached_with_the_page_s_answers(self)` (method)
- L340 `PreRestoreCopyTests` (class) — The copies of the data restores replaced are an undo: none goes before a
- L344 `setUp(self)` (method)
- L368 `_fake_backup(self, command, **kwargs)` (method) — morph_backup, as far as this needs: write the copy, then keep the newest ``keep``.
- L378 `_restore(self, archive)` (method)
- L384 `_left(self)` (method)
- L387 `test_restoring_the_oldest_copy_never_deletes_it(self)` (method)
- L391 `test_a_failed_restore_deletes_no_copy(self)` (method)
- L396 `test_after_a_restore_that_worked_the_newest_copies_are_kept(self)` (method)
- L402 `BackupMigrationsTests` (class) — Before anything runs, the screen says which migrations a backup lacks.
- L405 `_sqlite_backup(self, rows)` (method)
- L418 `test_a_sqlite_backup_s_migrations_are_read(self)` (method)
- L424 `test_a_postgres_backup_s_migrations_are_read_from_its_data(self)` (method)
- L444 `test_a_backup_whose_migrations_cannot_be_read_gives_none(self)` (method)
- L452 `test_the_running_code_s_missing_migrations_are_named(self)` (method)
