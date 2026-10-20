"""The release gate for migrations the previous release would trip over.

`manage.py release` refuses, and `release --check` (CI) fails, when a migration
the release adds would break the version before it (core/migration_safety.py).
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from core.migration_safety import Review, review_files

_BASE = Path(settings.BASE_DIR)
_REMOVES_FIELDS = 'core/migrations/0014_remove_storesettings_guided_ux_mode_and_more.py'
_STATE_ONLY_MOVE = 'plugins/installed/agent_core/migrations/0004_remove_agentapprovalrequest_decided_by_and_more.py'
_NEW_MODEL = 'core/migrations/0024_deployevent.py'
_RELEASE = 'core.management.commands.release'


class ReviewFilesTests(SimpleTestCase):
    def test_a_migration_that_removes_fields_blocks(self):
        reviews, unchecked = review_files(_BASE, [_REMOVES_FIELDS])
        self.assertEqual(unchecked, [])
        [result] = reviews
        self.assertTrue(result.blocks)
        self.assertIn('RemoveField storesettings.', ' '.join(result.findings))

    def test_a_state_only_move_in_the_repo_passes(self):
        reviews, unchecked = review_files(_BASE, [_STATE_ONLY_MOVE])
        self.assertEqual((unchecked, [r.findings for r in reviews]), ([], [()]))

    def test_a_new_model_passes(self):
        reviews, _ = review_files(_BASE, [_NEW_MODEL])
        self.assertFalse(reviews[0].blocks)

    def test_a_new_app_s_own_migrations_pass_together(self):
        # 0002_initial adds NOT NULL foreign keys to tables 0001 created.
        paths = [
            'plugins/installed/catalog/migrations/0001_initial.py',
            'plugins/installed/catalog/migrations/0002_initial.py',
        ]
        reviews, unchecked = review_files(_BASE, paths)
        self.assertEqual(unchecked, [])
        self.assertEqual([r.migration for r in reviews if r.blocks], [])

    def test_a_file_django_does_not_load_is_not_waved_through(self):
        path = 'plugins/installed/not_an_app/migrations/0001_initial.py'
        reviews, unchecked = review_files(_BASE, [path])
        self.assertEqual((reviews, unchecked), ([], [path]))


class AddedMigrationFilesTests(SimpleTestCase):
    """Against a throwaway repo, so it never depends on this checkout's state."""

    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        self.repo = Path(tmp)
        (self.repo / 'shop' / 'migrations').mkdir(parents=True)
        self.git('init', '-q', '-b', 'main')
        self.write('shop/migrations/0001_initial.py')
        self.git('add', '.')
        self.git('commit', '-qm', 'one')
        self.base = self.git('rev-parse', 'HEAD')
        patcher = mock.patch(f'{_RELEASE}._base_dir', return_value=self.repo)
        patcher.start()
        self.addCleanup(patcher.stop)

    def git(self, *args):
        env = {**os.environ, 'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@t',
               'GIT_COMMITTER_NAME': 't', 'GIT_COMMITTER_EMAIL': 't@t'}  # fmt: skip
        out = subprocess.run(
            ['git', *args], cwd=self.repo, check=True, capture_output=True, text=True, env=env
        )
        return out.stdout.strip()

    def write(self, rel):
        (self.repo / rel).write_text('# a migration\n')

    def test_staged_and_untracked_migrations_are_found(self):
        from core.management.commands.release import _added_migration_files

        self.write('shop/migrations/0002_committed.py')
        self.git('add', '.')
        self.git('commit', '-qm', 'two')
        self.write('shop/migrations/0003_staged.py')
        self.git('add', 'shop/migrations/0003_staged.py')
        self.write('shop/migrations/0004_untracked.py')
        self.write('shop/notes.py')  # not a migration
        self.assertEqual(
            _added_migration_files(self.base),
            [
                'shop/migrations/0002_committed.py',
                'shop/migrations/0003_staged.py',
                'shop/migrations/0004_untracked.py',
            ],
        )


class ReleaseGateTests(SimpleTestCase):
    def setUp(self):
        for target, value in (
            ('_diff_base', 'HEAD'),
            ('_added_migration_files', [_REMOVES_FIELDS]),
        ):
            patcher = mock.patch(f'{_RELEASE}.{target}', return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_release_check_fails_on_an_unsafe_migration(self):
        err = io.StringIO()
        with self.assertRaises(CommandError):
            call_command('release', check=True, stdout=io.StringIO(), stderr=err)
        self.assertIn(
            'core.0014_remove_storesettings_guided_ux_mode_and_more: RemoveField', err.getvalue()
        )
        self.assertIn('morpheus_contract', err.getvalue())
        # The safe recipe (owner's review, 2026-10-20): off the model first, then drop.
        self.assertIn('SeparateDatabaseAndState', err.getvalue())
        self.assertIn('db_default', err.getvalue())

    def test_release_refuses_before_writing_anything(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        settings_copy, notes_copy = tmp / 'settings.py', tmp / 'RELEASE_NOTES.md'
        shutil.copy(_BASE / 'morph/settings.py', settings_copy)
        shutil.copy(_BASE / 'docs/RELEASE_NOTES.md', notes_copy)
        before = (settings_copy.read_text(), notes_copy.read_text())
        with (
            mock.patch(f'{_RELEASE}._settings_path', return_value=settings_copy),
            mock.patch(f'{_RELEASE}._notes_path', return_value=notes_copy),
            self.assertRaises(CommandError),
        ):
            call_command(
                'release', '--patch', 'A change', stdout=io.StringIO(), stderr=io.StringIO()
            )
        self.assertEqual((settings_copy.read_text(), notes_copy.read_text()), before)

    def test_a_contract_lets_the_release_through_and_is_shown(self):
        accepted = Review(
            'core.0099_drop_x', ('RemoveField thing.x: …',), 'nothing reads x since v0.119.0'
        )
        out = io.StringIO()
        with mock.patch('core.migration_safety.review_files', return_value=([accepted], [])):
            call_command('release', check=True, stdout=out, stderr=io.StringIO())
        self.assertIn('core.0099_drop_x: nothing reads x since v0.119.0', out.getvalue())
