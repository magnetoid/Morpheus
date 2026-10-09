"""Whether GitHub has a newer Janus than the one the server runs (the Janus page).

pip writes what it resolved into the dist-info's ``direct_url.json``; on prod
(2026-10-09) that read ``{"url": "https://github.com/magnetoid/janus.git",
"vcs_info": {"commit_id": "eafb7ab…", "requested_revision": "main"}}``.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from plugins.installed.janus import upstream

COMMIT = 'eafb7aba34db8645401ce285edf987054c5d37d5'
NEWER = '0123456789abcdef0123456789abcdef01234567'


def _venv(root: Path, *, url='https://github.com/magnetoid/Janus-Agent.git', ref='main') -> Path:
    dist = root / 'lib' / 'python3.12' / 'site-packages' / 'janus_agent-0.18.0.dist-info'
    dist.mkdir(parents=True)
    (dist / 'METADATA').write_text('Metadata-Version: 2.4\nName: janus-agent\nVersion: 0.18.0\n')
    vcs = {'commit_id': COMMIT, 'vcs': 'git', **({'requested_revision': ref} if ref else {})}
    (dist / 'direct_url.json').write_text(json.dumps({'url': url, 'vcs_info': vcs}))
    (root / 'bin').mkdir()
    janus = root / 'bin' / 'janus'
    janus.write_text('#!/bin/sh\n')
    return janus


def _api(sha=NEWER, *, title='feat: something new\n\nbody', date='2026-10-10T08:00:00Z'):
    body = json.dumps({'sha': sha, 'commit': {'message': title, 'committer': {'date': date}}})
    return io.BytesIO(body.encode())


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class UpstreamCheckTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_latest_commit_is_read_once_a_day(self):
        with mock.patch.object(upstream, 'urlopen', return_value=_api()) as get:
            first = upstream.latest_commit('magnetoid/Janus-Agent', 'main')
            second = upstream.latest_commit('magnetoid/Janus-Agent', 'main')
        self.assertEqual(get.call_count, 1)
        self.assertEqual(first, second)
        self.assertEqual(first['sha'], NEWER)
        self.assertEqual(first['title'], 'feat: something new')
        url = get.call_args.args[0].full_url
        self.assertEqual(url, 'https://api.github.com/repos/magnetoid/Janus-Agent/commits/main')

    def test_a_failed_check_is_not_retried_on_every_page_view(self):
        with mock.patch.object(upstream, 'urlopen', side_effect=OSError('offline')) as get:
            self.assertIsNone(upstream.latest_commit('magnetoid/Janus-Agent', 'main'))
            self.assertIsNone(upstream.latest_commit('magnetoid/Janus-Agent', 'main'))
        self.assertEqual(get.call_count, 1)

    def test_only_github_repositories_are_checked(self):
        janus = _venv(self.root, url='https://gitlab.example/x/janus.git')
        with mock.patch.object(upstream, 'urlopen') as get:
            status = upstream.build_status([str(janus)])
        get.assert_not_called()
        self.assertEqual(status['state'], 'unknown')

    def test_states(self):
        janus = _venv(self.root)
        with mock.patch.object(upstream, 'urlopen', return_value=_api(sha=COMMIT)):
            self.assertEqual(upstream.build_status([str(janus)])['state'], 'current')
        cache.clear()
        with mock.patch.object(upstream, 'urlopen', return_value=_api()):
            status = upstream.build_status([str(janus)])
        self.assertEqual(status['state'], 'behind')
        self.assertEqual(status['latest']['sha'], NEWER)
        self.assertTrue(status['tracks_branch'])

    def test_a_pinned_build_is_compared_with_the_default_branch(self):
        janus = _venv(self.root, ref=COMMIT)
        with mock.patch.object(upstream, 'urlopen', return_value=_api()) as get:
            status = upstream.build_status([str(janus)])
        self.assertFalse(status['tracks_branch'])
        self.assertTrue(get.call_args.args[0].full_url.endswith('/commits/HEAD'))


class JanusPageBuildTests(TestCase):
    def setUp(self):
        cache.clear()
        user = get_user_model().objects.create_user(
            username='owner', email='owner@example.com', password='x', is_staff=True
        )
        self.client.force_login(user)

    @override_settings(LINDA_JANUS_AUTO_UPDATE=True)
    def test_page_shows_the_installed_commit_and_a_newer_one_on_github(self):
        status = {
            'version': '0.18.0',
            'commit': COMMIT,
            'ref': 'main',
            'repo': 'magnetoid/Janus-Agent',
            'url': 'https://github.com/magnetoid/Janus-Agent.git',
            'state': 'behind',
            'tracks_branch': True,
            'latest': {'sha': NEWER, 'title': 'feat: something new', 'date': '2026-10-10'},
        }
        from core.assistant import janus_runtime

        with (
            mock.patch.object(upstream, 'build_status', return_value=status),
            mock.patch.object(janus_runtime, 'maybe_update', return_value=False),
        ):
            response = self.client.get('/dashboard/apps/janus/engine/')
        self.assertContains(response, 'eafb7ab')
        self.assertContains(response, '0123456')
        self.assertContains(response, 'feat: something new')
        self.assertContains(response, 'Linda moves to it once it passes the compatibility check')

    def test_with_updates_off_the_page_says_the_next_deploy_brings_it(self):
        from plugins.models import PluginConfig

        PluginConfig.objects.update_or_create(
            plugin_name='janus', defaults={'config': {'auto_update': False}}
        )
        status = {
            'commit': COMMIT,
            'repo': 'magnetoid/Janus-Agent',
            'ref': 'main',
            'state': 'behind',
            'tracks_branch': True,
            'latest': {'sha': NEWER, 'title': 't', 'date': ''},
        }
        with mock.patch.object(upstream, 'build_status', return_value=status):
            response = self.client.get('/dashboard/apps/janus/engine/')
        self.assertContains(response, 'The next deploy installs it')

    def test_check_now_starts_the_updater(self):
        from core.assistant import janus_runtime

        with mock.patch.object(janus_runtime, 'maybe_update', return_value=True) as run:
            response = self.client.post(
                '/dashboard/apps/janus/engine/', {'action': 'check_updates'}
            )
        self.assertEqual(response.status_code, 302)
        run.assert_called_once_with(force=True)

    def test_page_shows_the_janus_in_use_and_its_contract(self):
        from core.assistant import janus_runtime

        report = {
            'ok': True,
            'checks': [
                {'name': 'toolset search', 'ok': True, 'required': True},
                {'name': 'tool hook events', 'ok': False, 'required': False},
            ],
            'notes': ['delegate_task still takes acp_command: subagents stay off'],
        }
        with mock.patch.object(janus_runtime, 'contract_report', return_value=report):
            response = self.client.get('/dashboard/apps/janus/engine/')
        self.assertContains(response, 'data-janus-updates')
        self.assertContains(response, '1 of 2 checks pass')
        self.assertContains(response, 'Display only: tool hook events')
        self.assertContains(response, 'subagents stay off')
