"""Restoring a backup from Settings → Version & updates (safe deploys, part 4)."""

from __future__ import annotations

import io
import json
import os
import tarfile
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.test import TestCase

from core import restore
from core.models import StoreSettings

VERSION_PAGE = '/dashboard/apps/release_notes/version/'
PRE = 'morpheus-backup-20261020T012146Z-v0.118.0-e1198af.tar.gz'
NIGHTLY = 'morpheus-backup-20261020T033000Z.tar.gz'
BEFORE = 'morpheus-backup-20261019T120000Z-before-restore.tar.gz'


def _write_archive(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, 'w:gz') as tar:
        info = tarfile.TarInfo('db.dump')
        info.size = 4
        tar.addfile(info, io.BytesIO(b'DUMP'))


class RestorePageTests(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        env = patch.dict(os.environ, {'MORPHEUS_BACKUP_DIR': tmp.name})
        env.start()
        self.addCleanup(env.stop)
        _write_archive(self.root / 'pre-deploy' / PRE)
        _write_archive(self.root / NIGHTLY)
        _write_archive(self.root / 'pre-restore' / BEFORE)
        (self.root / 'pre-deploy' / f'{PRE}.part').write_bytes(b'x')
        (self.root / 'notes.txt').write_text('x')
        row = StoreSettings.objects.first() or StoreSettings.objects.create()
        row.store_name = 'Test Shop'
        row.save()
        User = get_user_model()
        self.boss = User.objects.create_user(
            username='boss', email='b@x.io', password='pw', is_staff=True, is_superuser=True
        )
        self.crew = User.objects.create_user(
            username='crew', email='c@x.io', password='pw', is_staff=True
        )

    def _confirm_url(self, kind='pre-deploy', name=PRE):
        return f'/dashboard/restore/{kind}/{name}/'

    def test_the_templates_compile(self):
        get_template('release_notes/_backups_card.html')
        get_template('release_notes/restore_confirm.html')

    def test_superusers_see_every_backup_newest_first(self):
        self.client.force_login(self.boss)
        html = self.client.get(VERSION_PAGE).content.decode()
        self.assertIn('data-testid="backups"', html)
        self.assertLess(html.index(NIGHTLY), html.index(PRE))
        self.assertLess(html.index(PRE), html.index(BEFORE))
        for label in ('Nightly', 'Before an update', 'Before a restore'):
            self.assertIn(label, html)
        self.assertNotIn(f'{PRE}.part', html)
        self.assertNotIn('notes.txt', html)

    def test_staff_who_are_not_superusers_see_no_backups(self):
        self.client.force_login(self.crew)
        self.assertNotIn('data-testid="backups"', self.client.get(VERSION_PAGE).content.decode())
        self.assertEqual(self.client.get(self._confirm_url()).status_code, 404)

    def test_only_this_store_s_backup_folder_is_listed(self):
        # Staff and Linda can change the backups app's folder setting; a restore
        # trusts its file completely, so only MORPHEUS_BACKUP_DIR is listed.
        from plugins.registry import app_registry

        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        stray = 'morpheus-backup-20261020T100000Z.tar.gz'
        _write_archive(Path(other.name) / stray)
        app_registry.get('backups').set_config('backup_dir', other.name)
        self.client.force_login(self.boss)
        self.assertNotIn(stray, self.client.get(VERSION_PAGE).content.decode())
        self.assertEqual(self.client.get(self._confirm_url('nightly', stray)).status_code, 404)

    def test_names_outside_the_list_are_not_found(self):
        self.client.force_login(self.boss)
        for kind, name in (
            ('pre-deploy', f'{PRE}.part'),
            ('nightly', PRE),
            ('media', PRE),
            ('pre-deploy', 'morpheus-backup-20200101T000000Z.tar.gz'),
        ):
            self.assertEqual(
                self.client.get(self._confirm_url(kind, name)).status_code, 404, (kind, name)
            )

    def test_the_screen_names_what_the_restore_loses(self):
        self.client.force_login(self.boss)
        rows = [
            {'label': 'orders placed', 'count': 4},
            {'label': 'customers signed up', 'count': 2},
        ]
        with patch('core.restore.losses', return_value=rows):
            response = self.client.get(self._confirm_url())
        self.assertContains(response, '4 orders placed and 2 customers signed up')
        self.assertContains(response, 'Test Shop')
        self.assertContains(response, 'hx-boost="false"')

    def test_the_screen_says_so_when_nothing_was_counted(self):
        self.client.force_login(self.boss)
        with patch('core.restore.losses', return_value=[]):
            response = self.client.get(self._confirm_url())
        self.assertContains(response, 'No orders, customers or products have changed since then')

    def test_the_wrong_name_starts_nothing(self):
        self.client.force_login(self.boss)
        with patch('core.restore.spawn') as spawn:
            response = self.client.post(self._confirm_url(), {'confirm': 'test shop'})
        self.assertEqual(response.status_code, 400)
        # The message is a variable, so its apostrophes are escaped: match words without one.
        self.assertContains(response, 'Type it exactly as it is shown', status_code=400)
        spawn.assert_not_called()

    def test_the_right_name_starts_the_restore_in_the_background(self):
        self.client.force_login(self.boss)
        with patch('core.restore.spawn') as spawn:
            response = self.client.post(self._confirm_url(), {'confirm': ' Test Shop '})
        self.assertRedirects(response, VERSION_PAGE, fetch_redirect_response=False)
        spawn.assert_called_once_with(
            # The record names the person as the store signs them in: here, their email.
            self.root / 'pre-deploy' / PRE,
            confirm=' Test Shop ',
            by=self.boss.get_username(),
            reload_pid=0,
        )

    def test_under_gunicorn_the_web_workers_reload_afterwards(self):
        self.client.force_login(self.boss)
        with patch('core.restore.spawn') as spawn:
            self.client.post(
                self._confirm_url(), {'confirm': 'Test Shop'}, SERVER_SOFTWARE='gunicorn/26.0'
            )
        self.assertEqual(spawn.call_args.kwargs['reload_pid'], os.getppid())

    def test_a_restore_that_cannot_start_says_why(self):
        self.client.force_login(self.boss)
        with patch('core.restore.spawn', side_effect=OSError('no python')):
            response = self.client.post(self._confirm_url(), {'confirm': 'Test Shop'})
        self.assertContains(response, 'could not start', status_code=400)

    def test_the_page_shows_how_the_last_restore_ended(self):
        restore.state_dir().mkdir(parents=True)
        (restore.state_dir() / 'last.json').write_text(
            json.dumps(
                {
                    'state': 'done',
                    'file': PRE,
                    'kind': 'pre-deploy',
                    'by': 'boss',
                    'finished_at': '2026-10-20T17:05:00+00:00',
                    'pre_restore': BEFORE,
                    'missing': ['shop.0002_extra'],
                }
            )
        )
        self.client.force_login(self.boss)
        html = self.client.get(VERSION_PAGE).content.decode()
        self.assertIn('data-testid="restore-last"', html)
        self.assertIn('shop.0002_extra', html)
        self.assertIn('Redeploy the store', html)
        (restore.state_dir() / 'last.json').write_text(
            json.dumps({'state': 'failed', 'file': PRE, 'error': 'pg_restore said no'})
        )
        html = self.client.get(VERSION_PAGE).content.decode()
        self.assertIn('failed and changed nothing', html)
        self.assertIn('pg_restore said no', html)

    def test_a_restore_that_stopped_is_reported(self):
        path = restore.running_path()
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps({'state': 'running', 'file': PRE, 'started_at': '2026-10-20T17:00:00+00:00'})
        )
        stamp = time.time() - restore.STALE_AFTER - 5
        os.utime(path, (stamp, stamp))
        self.client.force_login(self.boss)
        self.assertContains(self.client.get(VERSION_PAGE), 'did not report back')
