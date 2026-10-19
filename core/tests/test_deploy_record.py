"""Each deploy is recorded as a DeployEvent (safe deploys, part 1).

safe_migrate writes it after migrating. The Version & updates page and Linda's
updates.status read it, and so will the rollback notice in release 4.
"""

from __future__ import annotations

import io
import os
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.db import DatabaseError
from django.test import TestCase

from core import deploys
from core.management.commands.morph_backup import Command as BackupCommand
from core.management.commands.safe_migrate import Command as SafeMigrate
from core.models import DeployEvent
from core.tests.test_safe_migrate import _DeployEnvMixin, _fake_dump


class RecordDeployTests(_DeployEnvMixin, TestCase):
    def test_a_deploy_is_recorded_with_its_backup_and_migrations(self):
        deploys.write_handoff(
            {'backup': '/app/backups/pre-deploy/b.tar.gz', 'migrations': ['core.0024_deployevent']}
        )
        event, created = deploys.record_deploy()
        self.assertTrue(created)
        self.assertEqual(
            (event.version, event.commit, event.backup, event.migrations),
            (
                settings.MORPHEUS_VERSION,
                'a' * 40,
                '/app/backups/pre-deploy/b.tar.gz',
                ['core.0024_deployevent'],
            ),
        )
        self.assertIsNone(deploys.read_handoff())

    def test_a_restart_of_the_same_deploy_adds_nothing(self):
        first, _ = deploys.record_deploy()
        deploys.write_handoff({'backup': '', 'migrations': []})
        event, created = deploys.record_deploy()
        self.assertFalse(created)
        self.assertEqual(event, first)
        self.assertEqual(DeployEvent.objects.count(), 1)

    def test_a_new_commit_is_a_new_deploy(self):
        deploys.record_deploy()
        with patch.dict(os.environ, {'SOURCE_COMMIT': 'c' * 40}):
            deploys.record_deploy()
        self.assertEqual([e.commit for e in DeployEvent.objects.all()], ['c' * 40, 'a' * 40])

    def test_migrating_again_on_the_same_commit_is_a_new_deploy(self):
        # The same commit deployed again after its database was restored to an
        # older copy: it migrates again, and that deserves its own row.
        deploys.record_deploy()
        deploys.write_handoff({'backup': '/b.tar.gz', 'migrations': ['core.0024_deployevent']})
        deploys.record_deploy()
        self.assertEqual(DeployEvent.objects.count(), 2)

    def test_an_unknown_commit_is_left_blank(self):
        with patch.dict(os.environ, {'SOURCE_COMMIT': 'not-a-sha'}):
            event, _ = deploys.record_deploy()
        self.assertEqual(event.commit, '')


class SafeMigrateRecordsTests(_DeployEnvMixin, TestCase):
    def test_a_deploy_that_migrates_is_recorded_with_its_backup(self):
        name = self.pend()
        out = io.StringIO()
        with (
            patch.object(BackupCommand, '_dump_database', _fake_dump),
            patch.object(SafeMigrate, '_migrate'),
        ):
            call_command('safe_migrate', stdout=out)
        event = DeployEvent.objects.get()
        [archive] = self.archives()
        self.assertEqual(event.backup, str(self.root / 'backups' / 'pre-deploy' / archive))
        self.assertEqual(event.migrations, [name])
        self.assertIn(
            f'Recorded {settings.MORPHEUS_VERSION} (aaaaaaa), 1 migrations', out.getvalue()
        )

    def test_a_failed_record_does_not_stop_the_store(self):
        err = io.StringIO()
        with (
            patch.object(SafeMigrate, '_migrate'),
            patch('core.deploys.record_deploy', side_effect=DatabaseError('down')),
            self.assertLogs('morpheus.deploys', 'ERROR'),
        ):
            call_command('safe_migrate', stdout=io.StringIO(), stderr=err)
        self.assertIn('Could not record this deploy', err.getvalue())
