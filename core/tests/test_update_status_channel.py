"""Status reads the signed channel first; a page load never fetches."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from core.signing import generate_keypair, sign_manifest
from core.updates import _UPDATE_STATUS_CACHE_KEY, platform_update_status

URL = 'https://updates.example.test/stable.json'
COMMIT = 'a' * 40


class _Resp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self, size=-1):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _serve(private, version='v9.0.0'):
    doc = sign_manifest(
        {'channel': 'stable', 'core': {'version': version, 'commit': COMMIT}}, private
    )
    return mock.patch(
        'core.update_sources.urllib.request.urlopen',
        return_value=_Resp(json.dumps(doc).encode()),
    )


class StatusChannelTests(SimpleTestCase):
    def setUp(self):
        self.priv, self.pub = generate_keypair()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        cache.delete(_UPDATE_STATUS_CACHE_KEY)
        self.addCleanup(cache.delete, _UPDATE_STATUS_CACHE_KEY)

    def _settings(self, version='v1.0.0', **extra):
        return override_settings(
            MORPHEUS_UPDATE_MANIFEST_URL=URL,
            MORPHEUS_UPDATE_PUBLIC_KEY=self.pub,
            MORPHEUS_VERSION=version,
            BASE_DIR=self.tmp,
            **extra,
        )

    def test_image_with_git_dir_but_no_git_reads_the_manifest(self):
        (self.tmp / '.git').mkdir()
        with (
            self._settings(),
            mock.patch('core.updates.shutil.which', return_value=None),
            _serve(self.priv),
        ):
            status = platform_update_status(fetch=True)
        self.assertEqual(status['available'], 'yes')
        self.assertEqual(status['latest'], 'v9.0.0')
        self.assertEqual(status['path'], 'manual')

    def test_clone_at_a_tag_without_upstream_reads_the_manifest(self):
        def git(*args):
            subprocess.run(['git', *args], cwd=self.tmp, check=True, capture_output=True)

        git('init', '-q')
        git('config', 'user.name', 't')
        git('config', 'user.email', 't@example.test')
        git('commit', '-q', '--allow-empty', '-m', 'one')
        git('tag', 'v1.0.0')
        with self._settings(), _serve(self.priv):
            status = platform_update_status(fetch=True)
        self.assertEqual(status['available'], 'yes')
        self.assertEqual(status['path'], 'git')

    def test_page_load_never_fetches(self):
        with self._settings(), mock.patch('core.update_sources.urllib.request.urlopen') as urlopen:
            status = platform_update_status(fetch=False)
        urlopen.assert_not_called()
        self.assertEqual(status['available'], 'unknown')
        self.assertEqual(status['path'], 'manual')

    def test_a_cached_git_status_is_not_shown_as_the_channel(self):
        cache.set(_UPDATE_STATUS_CACHE_KEY, {'source': 'git', 'available': 'no'}, 60)
        with self._settings():
            status = platform_update_status(fetch=False)
        self.assertEqual(status['available'], 'unknown')
        self.assertIn('Not checked yet', status['reason'])

    def test_a_cached_manifest_status_is_shown_on_a_page_load(self):
        cache.set(
            _UPDATE_STATUS_CACHE_KEY,
            {'source': 'manifest', 'available': 'yes', 'latest': 'v9.0.0', 'path': 'git'},
            60,
        )
        with self._settings():
            status = platform_update_status(fetch=False)
        self.assertEqual(status['available'], 'yes')
        self.assertEqual(status['path'], 'manual')

    def test_store_ahead_of_the_channel_is_up_to_date(self):
        with self._settings(version='v0.160.0'), _serve(self.priv, 'v0.159.0'):
            status = platform_update_status(fetch=True)
        self.assertEqual(status['available'], 'no')

    def test_checks_off_without_git_says_why(self):
        with (
            override_settings(MORPHEUS_UPDATE_MANIFEST_URL='off', BASE_DIR=self.tmp),
            mock.patch('core.update_sources.urllib.request.urlopen') as urlopen,
        ):
            status = platform_update_status(fetch=True)
        urlopen.assert_not_called()
        self.assertEqual(status['available'], 'unavailable')
        self.assertIn('off', status['reason'])
        self.assertEqual(status['path'], 'manual')

    def test_no_git_and_no_source_is_unavailable_with_a_path(self):
        with override_settings(
            MORPHEUS_UPDATE_MANIFEST_URL='', MORPHEUS_UPDATE_REPO='', BASE_DIR=self.tmp
        ):
            status = platform_update_status()
        self.assertEqual(status['available'], 'unavailable')
        self.assertEqual(status['path'], 'manual')


class StaleCacheAndOffTests(SimpleTestCase):
    def setUp(self):
        self.priv, self.pub = generate_keypair()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        cache.delete(_UPDATE_STATUS_CACHE_KEY)
        self.addCleanup(cache.delete, _UPDATE_STATUS_CACHE_KEY)

    def test_a_cached_yes_follows_the_running_version(self):
        cache.set(
            _UPDATE_STATUS_CACHE_KEY,
            {'source': 'manifest', 'available': 'yes', 'latest': 'v2.0.0', 'current': 'v1.0.0'},
            60,
        )
        with override_settings(
            MORPHEUS_UPDATE_MANIFEST_URL=URL,
            MORPHEUS_UPDATE_PUBLIC_KEY=self.pub,
            MORPHEUS_VERSION='v2.0.0',
            BASE_DIR=self.tmp,
        ):
            status = platform_update_status()
        self.assertEqual(status['available'], 'no')
        self.assertEqual(status['current'], 'v2.0.0')

    def test_a_cached_yes_stays_yes_while_behind(self):
        cache.set(
            _UPDATE_STATUS_CACHE_KEY,
            {'source': 'manifest', 'available': 'yes', 'latest': 'v2.0.0', 'current': 'v0.5.0'},
            60,
        )
        with override_settings(
            MORPHEUS_UPDATE_MANIFEST_URL=URL,
            MORPHEUS_UPDATE_PUBLIC_KEY=self.pub,
            MORPHEUS_VERSION='v1.0.0',
            BASE_DIR=self.tmp,
        ):
            status = platform_update_status()
        self.assertEqual((status['available'], status['current']), ('yes', 'v1.0.0'))

    def test_off_with_a_git_checkout_runs_no_git(self):
        (self.tmp / '.git').mkdir()
        for fetch in (True, False):
            with (
                self.subTest(fetch=fetch),
                override_settings(MORPHEUS_UPDATE_MANIFEST_URL='off', BASE_DIR=self.tmp),
                mock.patch('core.updates.shutil.which', return_value='/usr/bin/git'),
                mock.patch('core.updates._git') as git,
                mock.patch('core.updates.subprocess.run') as run,
                mock.patch('core.update_sources.urllib.request.urlopen') as urlopen,
            ):
                status = platform_update_status(fetch=fetch)
            git.assert_not_called()
            run.assert_not_called()
            urlopen.assert_not_called()
            self.assertEqual(status['source'], 'none')
            self.assertIn('switched off', status['reason'])
            self.assertEqual(status['path'], 'git')

    def test_a_repo_source_page_load_never_calls_github(self):
        with (
            override_settings(
                MORPHEUS_UPDATE_MANIFEST_URL='', MORPHEUS_UPDATE_REPO='o/r', BASE_DIR=self.tmp
            ),
            mock.patch('core.update_sources.urllib.request.urlopen') as urlopen,
        ):
            status = platform_update_status(fetch=False)
            cache.set(
                _UPDATE_STATUS_CACHE_KEY,
                {'source': 'github', 'available': 'yes', 'latest': 'v2.0.0'},
                60,
            )
            with override_settings(MORPHEUS_VERSION='v1.0.0'):
                cached = platform_update_status(fetch=False)
        urlopen.assert_not_called()
        self.assertEqual(status['available'], 'unknown')
        self.assertIn('Not checked yet', status['reason'])
        self.assertEqual((cached['available'], cached['latest']), ('yes', 'v2.0.0'))
        self.assertEqual(cached['path'], 'manual')

    def test_a_cached_github_yes_follows_the_running_version(self):
        cache.set(
            _UPDATE_STATUS_CACHE_KEY,
            {'source': 'github', 'available': 'yes', 'latest': 'v2.0.0', 'current': 'v1.0.0'},
            60,
        )
        with (
            override_settings(
                MORPHEUS_UPDATE_MANIFEST_URL='',
                MORPHEUS_UPDATE_REPO='o/r',
                MORPHEUS_VERSION='v2.0.0',
                BASE_DIR=self.tmp,
            ),
            mock.patch('core.update_sources.urllib.request.urlopen') as urlopen,
        ):
            status = platform_update_status(fetch=False)
        urlopen.assert_not_called()
        self.assertEqual((status['available'], status['current']), ('no', 'v2.0.0'))


class CheckCommandPathTests(SimpleTestCase):
    def test_update_line_names_the_path(self):
        status = {
            'available': 'yes',
            'latest': 'v9.0.0',
            'current': 'v1.0.0',
            'path': 'manual',
            'components': [],
        }
        out = StringIO()
        with mock.patch(
            'core.management.commands.morph_check_updates.platform_update_status',
            return_value=status,
        ):
            call_command('morph_check_updates', '--no-fetch', stdout=out)
        self.assertIn('latest v9.0.0 (deployed v1.0.0, path: manual).', out.getvalue())
