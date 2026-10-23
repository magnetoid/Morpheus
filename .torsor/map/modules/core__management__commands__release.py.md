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

# core/management/commands/release.py

Symbols in `core/management/commands/release.py`.

- L54 `_base_dir()` (function)
- L58 `_settings_path()` (function)
- L62 `_notes_path()` (function)
- L66 `parse_current_version(settings_text: str)` (function) — Return the `vX.Y.Z` currently declared as the MORPHEUS_VERSION default.
- L74 `bump(version: str, level: str)` (function) — Return the next version. `level` is 'major' | 'minor' | 'patch'.
- L91 `newest_notes_version(notes_text: str)` (function) — Return (version, date) of the newest release heading, or None.
- L97 `render_entry(version: str, date: str, summary: str, bullets: list[str])` (function) — Render one RELEASE_NOTES card, newest-first, with a trailing blank line.
- L108 `insert_entry(notes_text: str, entry: str)` (function) — Insert `entry` as the newest card — right after the intro `---` rule.
- L119 `set_settings_version(settings_text: str, new_version: str)` (function) — Return settings.py text with the MORPHEUS_VERSION default replaced.
- L124 `extract_section(notes_text: str, version: str)` (function) — Return one version's notes body (heading excluded), for a GitHub Release.
- L145 `_git(*args: str)` (function)
- L160 `_resolves(ref: str)` (function)
- L164 `_diff_base()` (function) — The ref to diff HEAD against.
- L186 `versioned_changes(changed_paths: list[str])` (function) — Filter a changed-file list down to the ones that require a bump.
- L200 `_added_migration_files(base: str)` (function) — Migration files new since ``base``: committed, staged, or not added to git
- L212 `_migration_report(base: str)` (function) — The release's new migrations, reviewed (core/migration_safety.py): the
- L240 `Command` (class)
- L243 `add_arguments(self, parser)` (method)
- L266 `handle(self, *args, **opts)` (method)
- L278 `_release(self, opts)` (method)
- L324 `_refuse_unsafe_migrations(self)` (method) — Stop the release before anything is written when its new migrations would
- L341 `_report_migrations(self, base: str)` (method)
- L347 `_check(self)` (method)
