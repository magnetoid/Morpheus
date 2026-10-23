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

# core/assistant/janus_learning.py

Symbols in `core/assistant/janus_learning.py`.

- L89 `Snapshot` (class) — What :func:`hydrate` wrote, so :func:`harvest` can tell what the turn changed.
- L96 `user_scope(user: Any)` (function) — The scope of one staff member's own notes, or '' when there is none.
- L103 `kind_of(path: str)` (function)
- L113 `_is_learning_path(path: str)` (function)
- L125 `_read_text(path: Path)` (function)
- L135 `_bundled_skill_names(home: Path)` (function)
- L140 `_skill_name(skill_md: str, dir_name: str)` (function)
- L149 `_walk_files(top: Path)` (function) — Files under ``top``, never following a symlink or entering a dot directory.
- L157 `_learned_skill_dirs(home: Path)` (function)
- L172 `remove_bundled_skills(home: Path)` (function) — Delete the general-purpose skills Janus copied into a home, and its manifest.
- L197 `scan(home: Path)` (function) — The learned files in a Janus home: relative path → text.
- L216 `_write(home: Path, rel: str, text: str)` (function)
- L232 `_remove(home: Path, rel: str)` (function)
- L247 `_rows(user_scope_: str)` (function)
- L254 `_wanted(row_scope: str, path: str, user_scope_: str)` (function)
- L262 `hydrate(home: Path, *, user: Any=None)` (function) — Make the home's learned files match the database. None if that failed.
- L283 `clear(home: Path)` (function) — Remove every learned file from a home (learning switched off).
- L292 `_entries(text: str | None)` (function)
- L296 `_merge_memory(base: str | None, turn: str | None, current: str | None)` (function)
- L304 `_lesson_records(text: str | None)` (function)
- L321 `_merge_lessons(base: str | None, turn: str | None, current: str | None)` (function)
- L333 `_journal_blocks(text: str)` (function) — A journal split into its heading and one block per entry (with continuation lines).
- L344 `_store_entries(text: str)` (function) — Only the journal entries about the store notes.
- L358 `_merge_journal(base: str | None, turn: str | None, current: str | None)` (function)
- L372 `merge(path: str, base: str | None, turn: str | None, current: str | None)` (function) — The file's new content after a turn changed it from ``base`` to ``turn``,
- L387 `harvest(home: Path, snapshot: Snapshot, *, conversation_key: str='', user: Any=None)` (function) — Store what the turn learned. Returns the paths that changed. Never raises.
- L398 `_harvest(home: Path, snapshot: Snapshot, *, conversation_key: str, user: Any)` (function)
- L463 `_prune_journal()` (function)
- L472 `_audit(event_type: str, user: Any, metadata: dict)` (function)
- L484 `note_id(entry: str)` (function)
- L488 `notes(*, user: Any=None)` (function) — Janus's notes about the store, and its notes about this staff member.
- L502 `forget_note(*, which: str, entry_id: str, user: Any=None)` (function) — Delete one note. ``which`` is 'store' or 'user' (the viewer's own notes).
- L531 `_scrub_journal(entry: str)` (function) — Remove a deleted note from the journal, or ``recall_memory`` would still find it.
- L552 `skills()` (function) — Skills Janus wrote, one entry per skill directory.
- L576 `delete_skill(skill_dir: str, *, user: Any=None)` (function)
- L589 `lesson_count()` (function)
- L596 `clear_lessons(*, user: Any=None)` (function)
