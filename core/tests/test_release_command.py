"""Tests for `manage.py release` — the version-bump writer + guard.

Covers the pure helpers (parse/bump/insert/extract) and the --check guard.
The command edits real repo files, so the write-path tests run against
in-memory strings via the module functions rather than touching disk.
"""

from __future__ import annotations

from django.core.management.base import CommandError
from django.test import TestCase

from core.management.commands.release import (
    bump,
    extract_section,
    insert_entry,
    newest_notes_version,
    parse_current_version,
    render_entry,
    set_settings_version,
    versioned_changes,
)

_SETTINGS = "MORPHEUS_VERSION = config('MORPHEUS_VERSION', default='v0.24.0')\n"

_NOTES = """# Morpheus OS — Release Notes

intro blurb

---

## v0.24.0 — 2026-07-19

**Agent hardening.**

- did a thing

## v0.23.0 — 2026-07-18

**Eco impact.**

- planted a tree
"""


class ParseAndBumpTests(TestCase):
    def test_parse_current_version(self) -> None:
        self.assertEqual(parse_current_version(_SETTINGS), 'v0.24.0')

    def test_parse_missing_raises(self) -> None:
        with self.assertRaises(CommandError):
            parse_current_version('nothing here')

    def test_bump_levels(self) -> None:
        self.assertEqual(bump('v0.24.0', 'patch'), 'v0.24.1')
        self.assertEqual(bump('v0.24.0', 'minor'), 'v0.25.0')
        self.assertEqual(bump('v0.24.3', 'major'), 'v1.0.0')

    def test_bump_rejects_non_semver(self) -> None:
        with self.assertRaises(CommandError):
            bump('0.24', 'patch')

    def test_set_settings_version_replaces_only_the_default(self) -> None:
        out = set_settings_version(_SETTINGS, 'v0.25.0')
        self.assertIn("default='v0.25.0'", out)
        self.assertNotIn('v0.24.0', out)


class NotesTests(TestCase):
    def test_newest_notes_version(self) -> None:
        self.assertEqual(newest_notes_version(_NOTES), ('v0.24.0', '2026-07-19'))

    def test_newest_notes_none_when_absent(self) -> None:
        self.assertIsNone(newest_notes_version('# just a title\n'))

    def test_render_entry_shape(self) -> None:
        entry = render_entry('v0.25.0', '2026-07-20', 'Big thing', ['one', 'two'])
        self.assertTrue(entry.startswith('## v0.25.0 — 2026-07-20\n'))
        self.assertIn('**Big thing**', entry)
        self.assertIn('- one', entry)
        self.assertIn('- two', entry)

    def test_insert_entry_lands_newest_first(self) -> None:
        entry = render_entry('v0.25.0', '2026-07-20', 'New', [])
        out = insert_entry(_NOTES, entry)
        # The new heading appears before the previously-newest one.
        self.assertLess(out.index('## v0.25.0'), out.index('## v0.24.0'))
        # Intro is preserved above the first release.
        self.assertLess(out.index('intro blurb'), out.index('## v0.25.0'))

    def test_insert_requires_separator(self) -> None:
        with self.assertRaises(CommandError):
            insert_entry('# no separator here\n', 'x')

    def test_extract_section_returns_only_that_version(self) -> None:
        body = extract_section(_NOTES, 'v0.24.0')
        self.assertIn('Agent hardening', body)
        self.assertNotIn('Eco impact', body)  # stops at the next heading

    def test_extract_missing_version_raises(self) -> None:
        with self.assertRaises(CommandError):
            extract_section(_NOTES, 'v9.9.9')


class VersionedChangesTests(TestCase):
    def test_app_and_theme_paths_count(self) -> None:
        changed = versioned_changes(
            [
                'core/agents/llm.py',
                'plugins/installed/orders/services.py',
                'themes/library/dot_books/templates/x.html',
                'morph/settings.py',
            ]
        )
        self.assertEqual(len(changed), 4)

    def test_non_shipping_and_tests_are_excluded(self) -> None:
        self.assertEqual(
            versioned_changes(
                [
                    'docs/RELEASE_NOTES.md',
                    'scripts/deploy_smoke.sh',
                    '.github/workflows/ci.yml',
                    'core/self_improvement/tests/test_services.py',
                    'README.md',
                ]
            ),
            [],
        )
