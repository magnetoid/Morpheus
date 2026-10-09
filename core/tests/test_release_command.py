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


class DiffBaseTests(TestCase):
    """`_diff_base` on main itself: the origin/main merge-base IS HEAD, so the
    old logic diffed HEAD against HEAD, saw nothing, and a direct push that
    skipped the bump went green (02f239f shipped a theme change unversioned).
    Runs against a throwaway repo so it never depends on this checkout's state.
    """

    def setUp(self) -> None:
        import os
        import subprocess
        import tempfile
        from pathlib import Path
        from unittest import mock

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        repo = Path(self._tmp.name)

        def git(*args: str) -> str:
            return subprocess.run(
                ['git', *args],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    'GIT_AUTHOR_NAME': 't',
                    'GIT_AUTHOR_EMAIL': 't@t',
                    'GIT_COMMITTER_NAME': 't',
                    'GIT_COMMITTER_EMAIL': 't@t',
                },
            ).stdout.strip()

        git('init', '-q', '-b', 'main')
        (repo / 'a.txt').write_text('1')
        git('add', '.')
        git('commit', '-qm', 'one')
        self.first = git('rev-parse', 'HEAD')
        (repo / 'a.txt').write_text('2')
        git('commit', '-qam', 'two')
        # Make origin/main point at HEAD — the on-main-after-push situation.
        git('update-ref', 'refs/remotes/origin/main', 'HEAD')

        p = mock.patch('core.management.commands.release._base_dir', return_value=repo)
        p.start()
        self.addCleanup(p.stop)
        env = mock.patch.dict(os.environ, {'RELEASE_CHECK_BASE': ''})
        env.start()
        self.addCleanup(env.stop)

    def test_on_main_diffs_against_parent_not_itself(self) -> None:
        from core.management.commands.release import _diff_base

        self.assertEqual(_diff_base(), 'HEAD~1')

    def test_explicit_push_base_wins(self) -> None:
        import os
        from unittest import mock

        from core.management.commands.release import _diff_base

        with mock.patch.dict(os.environ, {'RELEASE_CHECK_BASE': self.first}):
            self.assertEqual(_diff_base(), self.first)

    def test_zero_or_unknown_push_base_is_ignored(self) -> None:
        import os
        from unittest import mock

        from core.management.commands.release import _diff_base

        for bogus in ('0' * 40, 'deadbeef' * 5):
            with mock.patch.dict(os.environ, {'RELEASE_CHECK_BASE': bogus}):
                self.assertEqual(_diff_base(), 'HEAD~1', bogus)
