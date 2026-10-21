"""A store put back on an older release says so, once (safe deploys, part 3)."""

from __future__ import annotations

import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase, override_settings

from core import deploys
from core.management.commands.morph_backup import Command as BackupCommand
from core.management.commands.safe_migrate import Command as SafeMigrate
from core.models import DeployEvent
from core.tests.test_safe_migrate import _broken_dump, _DeployEnvMixin, _fake_dump

RUNNING = 'v0.121.0'


class VersionTests(SimpleTestCase):
    def test_versions_compare_as_numbers(self):
        self.assertTrue(deploys.is_older('v0.9.9', 'v0.10.0'))
        self.assertTrue(deploys.is_older('v0.120.1', 'v0.121.0'))
        self.assertFalse(deploys.is_older('v0.121.0', 'v0.121.0'))
        self.assertFalse(deploys.is_older('v0.122.0', 'v0.121.0'))

    def test_an_unparsable_version_is_never_older(self):
        self.assertFalse(deploys.is_older('dev', 'v0.121.0'))
        self.assertFalse(deploys.is_older('v0.120.0', 'nightly'))
        self.assertIsNone(deploys.version_key('v1.0.0-rc1'))


@override_settings(MORPHEUS_VERSION=RUNNING)
class RecordTests(_DeployEnvMixin, TestCase):
    def test_an_older_version_after_a_newer_deploy_is_a_rollback(self):
        DeployEvent.objects.create(version='v0.122.0', commit='b' * 40)
        event, created = deploys.record_deploy()
        self.assertTrue(created)
        self.assertEqual(event.rolled_back_from, 'v0.122.0')

    def test_a_newer_version_is_not_a_rollback(self):
        DeployEvent.objects.create(version='v0.120.1', commit='b' * 40)
        event, _ = deploys.record_deploy()
        self.assertEqual(event.rolled_back_from, '')

    def test_the_marker_names_the_row_this_container_wrote(self):
        event, _ = deploys.record_deploy()
        marker = deploys.read_handoff()
        self.assertEqual((marker['recorded'], marker['version']), (event.pk, RUNNING))

    def test_the_failed_release_s_backup_is_found_by_its_version(self):
        DeployEvent.objects.create(
            version='v0.122.0', commit='b' * 40, backup='/app/backups/pre-deploy/x.tar.gz'
        )
        self.assertEqual(deploys.failed_backup_name('v0.122.0'), 'x.tar.gz')
        self.assertEqual(deploys.failed_backup_name('v0.130.0'), '')

    def test_the_backup_named_is_the_first_one_that_release_took(self):
        # A second container of the same release backs up a half-migrated database.
        DeployEvent.objects.create(
            version='v0.122.0', commit='b' * 40, backup='/app/backups/pre-deploy/first.tar.gz'
        )
        DeployEvent.objects.create(
            version='v0.122.0', commit='b' * 40, backup='/app/backups/pre-deploy/second.tar.gz'
        )
        self.assertEqual(deploys.failed_backup_name('v0.122.0'), 'first.tar.gz')


@override_settings(MORPHEUS_VERSION=RUNNING)
class SafeMigrateOrderTests(_DeployEnvMixin, TestCase):
    def _run(self, migrate=None, record=None, alert=None):
        out = io.StringIO()
        patches = [
            patch.object(BackupCommand, '_dump_database', _fake_dump),
            patch.object(SafeMigrate, '_migrate', side_effect=migrate),
            patch('core.errors.alerts.send_alert', side_effect=alert, return_value=True),
        ]
        if record is not None:
            patches.append(patch('core.deploys.record_deploy', side_effect=record))
        mocks = [p.start() for p in patches]
        try:
            call_command('safe_migrate', stdout=out)
        finally:
            for p in patches:
                p.stop()
        return out.getvalue(), mocks[2]

    def test_the_attempt_is_recorded_before_migrating(self):
        self.pend()

        def boom():
            raise RuntimeError('migrate failed')

        with self.assertRaises(RuntimeError):
            self._run(migrate=boom)
        event = DeployEvent.objects.get()
        self.assertEqual(event.version, RUNNING)
        self.assertTrue(event.backup)  # the copy from just before it, for the rollback notice

    def test_a_restart_after_a_crashed_migration_adds_no_row(self):
        self.pend()

        def boom():
            raise RuntimeError('migrate failed')

        with self.assertRaises(RuntimeError):
            self._run(migrate=boom)
        self._run()
        self.assertEqual(DeployEvent.objects.count(), 1)

    def test_a_record_that_cannot_be_written_yet_is_written_after_migrating(self):
        calls = []

        def record():
            calls.append('record')
            if len(calls) == 1:
                raise DatabaseError('no such column: rolled_back_from')
            return DeployEvent.objects.create(version=RUNNING, commit='a' * 40), True

        def migrate():
            calls.append('migrate')

        self._run(migrate=migrate, record=record)
        self.assertEqual(calls, ['record', 'migrate', 'record'])

    def test_the_operators_hear_once(self):
        DeployEvent.objects.create(
            version='v0.122.0', commit='b' * 40, backup='/app/backups/pre-deploy/x.tar.gz'
        )
        out, alert = self._run()
        alert.assert_called_once()
        subject, body = alert.call_args.args
        self.assertIn('v0.122.0', subject)
        self.assertIn(RUNNING, subject)
        self.assertIn('x.tar.gz', body)
        self.assertIn('do not redeploy', body)
        self.assertIn('after v0.122.0', out)
        _, alert_again = self._run()  # a restart of the rolled-back container
        alert_again.assert_not_called()

    def test_the_operators_hear_once_the_store_has_migrated(self):
        # The email must never stop or slow the boot that brings the store back.
        DeployEvent.objects.create(version='v0.122.0', commit='b' * 40)
        order = []

        def alert(subject, body, **kwargs):
            order.append('email')
            return True

        self._run(migrate=lambda: order.append('migrate'), alert=alert)
        self.assertEqual(order, ['migrate', 'email'])

    def test_an_email_that_fails_does_not_stop_the_boot(self):
        DeployEvent.objects.create(version='v0.122.0', commit='b' * 40)
        with patch('core.deploys.notify_rollback', side_effect=DatabaseError('no such table')):
            out, _ = self._run()
        self.assertIn('could not email the operators', out)
        self.assertIsNone(deploys.read_handoff())


@override_settings(
    MORPHEUS_VERSION=RUNNING,
    EMAIL_BACKEND='core.email.MorpheusEmailBackend',
    EMAIL_HOST='smtp.example.test',
    ERROR_ALERT_EMAILS='ops@example.test',
)
class RollbackEmailTests(_DeployEnvMixin, TestCase):
    def test_the_email_gives_up_on_a_mail_server_that_does_not_answer(self):
        event = DeployEvent.objects.create(
            version=RUNNING, commit='a' * 40, rolled_back_from='v0.122.0'
        )
        with patch('django.core.mail.backends.smtp.smtplib.SMTP') as smtp:
            self.assertTrue(deploys.notify_rollback(event))
        self.assertEqual(smtp.call_args.kwargs.get('timeout'), 10)


@override_settings(MORPHEUS_VERSION=RUNNING)
class FailedBackupTests(_DeployEnvMixin, TestCase):
    def _fail(self):
        with (
            patch.object(BackupCommand, '_dump_database', _broken_dump),
            patch.object(SafeMigrate, '_migrate') as migrated,
            self.assertRaises(CommandError),
        ):
            call_command('safe_migrate', stdout=io.StringIO())
        migrated.assert_not_called()

    def test_a_failed_backup_leaves_the_attempt_for_the_rollback_notice(self):
        name = self.pend()
        self._fail()
        self._fail()  # the crash loop that follows adds no second row
        event = DeployEvent.objects.get()
        self.assertEqual((event.version, event.backup, event.migrations), (RUNNING, '', [name]))
        self.assertIsNone(deploys.read_handoff())  # so the next boot tries the backup again
        with override_settings(MORPHEUS_VERSION='v0.120.1'):
            rolled, _ = deploys.record_deploy()
        self.assertEqual(rolled.rolled_back_from, RUNNING)


@override_settings(MORPHEUS_VERSION=RUNNING)
class RunningReleaseTests(_DeployEnvMixin, TestCase):
    def test_the_page_names_the_rollback_and_the_failed_backup(self):
        DeployEvent.objects.create(
            version='v0.122.0', commit='b' * 40, backup='/app/backups/pre-deploy/x.tar.gz'
        )
        deploys.record_deploy()
        running = deploys.running_release()
        self.assertEqual(
            (running['rolled_back_from'], running['failed_backup']), ('v0.122.0', 'x.tar.gz')
        )

    def test_the_card_says_the_store_was_put_back(self):
        DeployEvent.objects.create(version='v0.122.0', commit='b' * 40)
        deploys.record_deploy()
        staff = get_user_model().objects.create_user(
            username='boss', email='b@x.io', password='pw', is_staff=True
        )
        self.client.force_login(staff)
        html = self.client.get('/dashboard/apps/release_notes/version/').content.decode()
        self.assertIn('data-testid="rolled-back"', html)
        self.assertIn('v0.122.0 did not come up', html)
