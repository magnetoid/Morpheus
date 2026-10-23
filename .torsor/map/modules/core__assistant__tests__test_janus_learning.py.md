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

# core/assistant/tests/test_janus_learning.py

Symbols in `core/assistant/tests/test_janus_learning.py`.

- L28 `_home()` (function)
- L33 `_put(home: Path, rel: str, text: str)` (function)
- L43 `_entry(note: str, *, scope: str='MEMORY', event: str='added')` (function) — One journal line as tools/memory_tool.py:append_daily_snapshot writes it.
- L49 `_skill(name: str, description: str='Does a thing')` (function)
- L53 `MergeTests` (class) — Two conversations can learn at once; neither may erase the other.
- L56 `test_memory_notes_added_concurrently_are_both_kept(self)` (method)
- L63 `test_memory_note_removed_in_the_turn_is_removed(self)` (method)
- L67 `test_memory_note_replaced_in_the_turn(self)` (method)
- L70 `test_last_note_removed_deletes_the_file(self)` (method)
- L73 `test_lessons_merge_by_id(self)` (method)
- L86 `test_unreadable_lessons_keep_what_is_stored(self)` (method)
- L91 `test_journal_merges_by_appended_entries(self)` (method)
- L96 `test_journal_never_keeps_entries_about_a_person(self)` (method)
- L105 `test_skill_file_changed_in_the_turn_wins(self)` (method)
- L108 `test_skill_file_deleted_in_the_turn_is_deleted(self)` (method)
- L111 `test_deletion_does_not_erase_someone_elses_newer_edit(self)` (method)
- L115 `ScanTests` (class) — Only what Janus learned is kept — never its bundled skills or anything executable.
- L118 `setUp(self)` (method)
- L122 `test_learned_files_are_found(self)` (method)
- L139 `test_bundled_skills_are_not_learned(self)` (method)
- L145 `test_scripts_hidden_files_and_locks_are_not_kept(self)` (method)
- L153 `test_symlinks_are_not_followed(self)` (method)
- L161 `test_oversized_file_is_not_kept(self)` (method)
- L166 `SyncTests` (class)
- L167 `setUp(self)` (method)
- L176 `_fresh_home(self)` (method)
- L181 `_learn(self, files: dict[str, str | None], *, user=None, home=None, key='conv-1')` (method) — One turn: hydrate, let 'Janus' change files, harvest.
- L192 `test_learning_survives_a_wiped_home(self)` (method)
- L213 `test_hydrated_memory_round_trips_the_way_janus_checks_it(self)` (method)
- L223 `test_two_conversations_learning_at_once_keep_both(self)` (method)
- L235 `test_notes_about_a_person_stay_with_that_person(self)` (method)
- L247 `test_without_a_staff_member_no_personal_notes_are_kept(self)` (method)
- L252 `test_hydrate_removes_what_the_merchant_deleted(self)` (method)
- L259 `test_a_turn_cannot_author_a_flood_of_skill_files(self)` (method)
- L269 `test_a_stored_path_cannot_escape_the_home(self)` (method)
- L277 `test_what_a_turn_learned_is_audited_with_the_human(self)` (method)
- L286 `test_review_deletes_one_note(self)` (method)
- L292 `test_a_deleted_note_is_also_gone_from_the_journal(self)` (method)
- L308 `test_a_persons_journal_entry_never_reaches_a_colleague(self)` (method)
- L320 `test_review_lists_skills_with_their_description(self)` (method)
- L334 `_FakeJanus` (class) — Stands in for the `janus chat` process: sees the home, writes what it learned.
- L337 `__init__(self, writes=None, raise_timeout=False)` (method)
- L343 `__call__(self, argv, **kwargs)` (method)
- L354 `EngineLearningTests` (class) — The real turn path with an unpatched home directory — only the process is fake.
- L357 `setUp(self)` (method)
- L365 `_turn(self, fake, *, key, home)` (method)
- L375 `test_a_note_from_one_conversation_reaches_the_next_after_a_redeploy(self)` (method)
- L385 `test_what_was_saved_before_a_timeout_is_kept(self)` (method)
- L394 `test_an_abandoned_turn_does_not_store_half_written_learning(self)` (method)
- L421 `test_learning_switched_off_keeps_nothing_and_loads_nothing(self)` (method)
