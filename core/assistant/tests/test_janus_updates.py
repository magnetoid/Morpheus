"""Janus keeps itself current from GitHub, and only ever switches to a build that
keeps Morpheus's contract.

Verified on prod before building (2026-10-09): pip installs Janus from GitHub's
archive of a commit in 29 s with no git in the image (226 MB), and the contract
script runs against an install in 2 s.
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from core.assistant import janus_runtime as rt
from core.assistant import janus_updater as up

OLD = 'eafb7aba34db8645401ce285edf987054c5d37d5'
NEW = '0123456789abcdef0123456789abcdef01234567'


def _venv(root: Path, sha: str, *, marker: dict | None = None, url: str | None = None) -> Path:
    """A fake Janus venv: bin/janus plus the dist-info pip would write."""
    dist = root / 'lib' / 'python3.12' / 'site-packages' / 'janus_agent-0.18.0.dist-info'
    dist.mkdir(parents=True)
    (dist / 'METADATA').write_text('Name: janus-agent\nVersion: 0.18.0\n', encoding='utf-8')
    origin = (
        {'url': url, 'archive_info': {}}
        if url
        else {
            'url': 'https://github.com/magnetoid/Janus-Agent.git',
            'vcs_info': {'commit_id': sha, 'requested_revision': 'main', 'vcs': 'git'},
        }
    )
    (dist / 'direct_url.json').write_text(json.dumps(origin), encoding='utf-8')
    (root / 'bin').mkdir()
    janus = root / 'bin' / 'janus'
    janus.write_text('#!/bin/sh\n', encoding='utf-8')
    janus.chmod(0o755)
    if marker is not None:
        (root / rt.BUILD_FILE).write_text(json.dumps(marker), encoding='utf-8')
    return janus


def _github(sha=NEW, title='feat: faster tools'):
    body = {
        'sha': sha,
        'commit': {'message': f'{title}\n\nmore', 'committer': {'date': '2026-10-10T08:00:00Z'}},
    }
    return io.BytesIO(json.dumps(body).encode())


class InstalledBuildTests(SimpleTestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_the_image_build_is_read_from_pips_git_record(self):
        build = rt.installed_build(str(_venv(self.root / 'image', OLD)))
        self.assertEqual(
            (build['commit'], build['ref'], build['repo'], build['source']),
            (OLD, 'main', 'magnetoid/Janus-Agent', 'image'),
        )

    def test_an_auto_installed_build_is_read_from_the_archive_url_and_marker(self):
        url = f'https://github.com/magnetoid/Janus-Agent/archive/{NEW}.tar.gz'
        janus = _venv(self.root / 'auto', NEW, marker={'commit': NEW, 'ref': 'main'}, url=url)
        build = rt.installed_build(str(janus))
        self.assertEqual(
            (build['commit'], build['ref'], build['repo'], build['source']),
            (NEW, 'main', 'magnetoid/Janus-Agent', 'auto'),
        )


class _EngineDirMixin:
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / 'engine'
        self.root.mkdir()
        patcher = mock.patch.object(rt, 'engine_dir', return_value=self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _activate(self, sha=NEW, *, previous=None, failures=0):
        janus = _venv(self.root / 'venvs' / sha[:12], sha, marker={'commit': sha, 'ref': 'main'})
        state = {
            'active': {'commit': sha, 'bin': str(janus), 'failures': failures},
            'previous': previous,
        }
        (self.root / 'state.json').write_text(json.dumps(state), encoding='utf-8')
        return janus


@override_settings(LINDA_JANUS_AUTO_UPDATE=True)
class ActiveBinTests(_EngineDirMixin, TestCase):
    def test_a_verified_auto_install_is_used(self):
        janus = self._activate()
        self.assertEqual(rt.active_bin(), str(janus.resolve()))

    def test_nothing_installed_means_the_image_janus(self):
        self.assertIsNone(rt.active_bin())

    def test_a_venv_without_its_verification_marker_is_ignored(self):
        janus = self._activate()
        (janus.parent.parent / rt.BUILD_FILE).unlink()
        self.assertIsNone(rt.active_bin())

    def test_a_path_outside_the_engine_dir_is_ignored(self):
        # state.json names the binary; it must never point Linda at another program.
        with TemporaryDirectory() as other:
            janus = _venv(Path(other), NEW, marker={'commit': NEW})
            (self.root / 'state.json').write_text(
                json.dumps({'active': {'commit': NEW, 'bin': str(janus)}}), encoding='utf-8'
            )
            self.assertIsNone(rt.active_bin())

    @override_settings(LINDA_JANUS_AUTO_UPDATE=False)
    def test_the_deployment_switch_turns_it_off(self):
        self._activate()
        self.assertIsNone(rt.active_bin())

    def test_the_merchant_switch_turns_it_off(self):
        from plugins.models import PluginConfig

        self._activate()
        PluginConfig.objects.update_or_create(
            plugin_name='janus', defaults={'config': {'auto_update': False}}
        )
        self.assertIsNone(rt.active_bin())

    def test_the_engine_runs_the_auto_installed_janus(self):
        from core.assistant import janus_engine as eng

        janus = self._activate()
        with override_settings(JANUS_BIN=''):
            self.assertEqual(eng.janus_cmd(), [str(janus.resolve())])

    def test_an_explicit_janus_bin_still_wins(self):
        from core.assistant import janus_engine as eng

        self._activate()
        with override_settings(JANUS_BIN='/opt/custom/janus'):
            self.assertEqual(eng.janus_cmd(), ['/opt/custom/janus'])


@override_settings(LINDA_JANUS_AUTO_UPDATE=True)
class MaybeUpdateTests(_EngineDirMixin, TestCase):
    def _source(self, ref='main'):
        return mock.patch.object(
            rt,
            'source',
            return_value={'repo': 'magnetoid/Janus-Agent', 'ref': ref, 'image_commit': OLD},
        )

    def test_a_due_check_starts_the_updater_in_the_background(self):
        with self._source(), mock.patch.object(rt.subprocess, 'Popen') as popen:
            self.assertTrue(rt.maybe_update())
        argv = popen.call_args.args[0]
        self.assertEqual(argv[1:3], ['-I', str(rt.UPDATER)])
        self.assertEqual(argv[argv.index('--repo') + 1], 'magnetoid/Janus-Agent')
        self.assertEqual(argv[argv.index('--ref') + 1], 'main')
        self.assertEqual(argv[argv.index('--image-commit') + 1], OLD)
        self.assertIn('ddgs==9.16.0', argv)
        self.assertTrue(popen.call_args.kwargs['start_new_session'])
        env = popen.call_args.kwargs['env']
        self.assertNotIn('DATABASE_URL', env)
        self.assertNotIn('SECRET_KEY', env)

    def test_checks_are_spaced_out(self):
        with self._source(), mock.patch.object(rt.subprocess, 'Popen') as popen:
            self.assertTrue(rt.maybe_update())
            self.assertFalse(rt.maybe_update())
            self.assertTrue(rt.maybe_update(force=True))
        self.assertEqual(popen.call_count, 2)
        self.assertIn('--force', popen.call_args.args[0])

    def test_a_build_pinned_to_a_commit_is_never_auto_updated(self):
        janus = _venv(Path(self._tmp.name) / 'image', OLD)
        dist = next((janus.parent.parent).glob('lib/*/site-packages/*.dist-info'))
        (dist / 'direct_url.json').write_text(
            json.dumps(
                {
                    'url': 'https://github.com/magnetoid/Janus-Agent.git',
                    'vcs_info': {'commit_id': OLD, 'requested_revision': OLD},
                }
            ),
            encoding='utf-8',
        )
        with mock.patch.object(rt, 'image_bin', return_value=str(janus)):
            self.assertIsNone(rt.source())
        with (
            mock.patch.object(rt, 'image_bin', return_value=str(janus)),
            mock.patch.object(rt.subprocess, 'Popen') as popen,
        ):
            self.assertFalse(rt.maybe_update(force=True))
        popen.assert_not_called()

    def test_the_image_branch_is_the_update_source(self):
        janus = _venv(Path(self._tmp.name) / 'image', OLD)
        with mock.patch.object(rt, 'image_bin', return_value=str(janus)):
            self.assertEqual(
                rt.source(), {'repo': 'magnetoid/Janus-Agent', 'ref': 'main', 'image_commit': OLD}
            )

    def test_a_failure_to_start_never_reaches_the_turn(self):
        with self._source(), mock.patch.object(rt.subprocess, 'Popen', side_effect=OSError('no')):
            self.assertFalse(rt.maybe_update())


@override_settings(LINDA_JANUS_AUTO_UPDATE=True)
class RollbackTests(_EngineDirMixin, TestCase):
    def _state(self):
        return json.loads((self.root / 'state.json').read_text(encoding='utf-8'))

    def test_three_engine_failures_in_a_row_put_the_previous_janus_back(self):
        previous = {'commit': OLD, 'bin': '/elsewhere/janus'}
        self._activate(previous=previous)
        for _ in range(rt.ROLLBACK_AFTER):
            rt.record_turn(error='janus exit 1')
        state = self._state()
        self.assertEqual(state['active'], previous)
        self.assertIn(NEW, state['failed'])
        self.assertEqual(state['last_check']['result'], 'rolled_back')

    def test_a_success_resets_the_count(self):
        self._activate()
        rt.record_turn(error='janus exit 1')
        rt.record_turn(error='janus exit 1')
        rt.record_turn(error='')
        rt.record_turn(error='janus exit 1')
        self.assertEqual(self._state()['active']['commit'], NEW)

    def test_provider_trouble_and_timeouts_say_nothing_about_the_build(self):
        self._activate()
        for error in (
            'janus timed out after 240s',
            'janus exit 1: 401 Unauthorized',
            'HTTP 429 rate limit',
        ):
            for _ in range(rt.ROLLBACK_AFTER):
                rt.record_turn(error=error)
        self.assertEqual(self._state()['active']['commit'], NEW)

    def test_an_engine_failure_that_mentions_generating_still_counts(self):
        # 'generate' contains 'rate'; a rate-limit filter on the bare word let
        # every "failed to generate" crash through without a rollback.
        self._activate(previous={'commit': OLD, 'bin': '/elsewhere/janus'})
        for _ in range(rt.ROLLBACK_AFTER):
            rt.record_turn(error='janus exit 1: failed to generate a reply')
        self.assertEqual(self._state()['active']['commit'], OLD)

    def test_the_image_janus_is_never_rolled_back(self):
        rt.record_turn(error='janus exit 1')
        self.assertFalse((self.root / 'state.json').exists())


class UpdaterTests(SimpleTestCase):
    """The detached updater, with GitHub and pip faked."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _args(self, **kw):
        base = {
            'engine_dir': str(self.root),
            'repo': 'magnetoid/Janus-Agent',
            'ref': 'main',
            'image_commit': OLD,
            'contract': '/app/core/assistant/janus_contract.py',
            'pin': ['ddgs==9.16.0'],
            'force': False,
        }
        return argparse.Namespace(**{**base, **kw})

    def _fake_tools(self, contract_ok=True, pip_rc=0):
        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            if argv[1:3] == ['-m', 'venv']:
                Path(argv[3], 'bin').mkdir(parents=True, exist_ok=True)
                Path(argv[3], 'bin', 'janus').write_text('')
                return subprocess.CompletedProcess(argv, 0, '', '')
            if argv[0].endswith('/pip'):
                return subprocess.CompletedProcess(
                    argv, pip_rc, '', 'pip exploded' if pip_rc else ''
                )
            report = {
                'ok': contract_ok,
                'version': '0.19.0',
                'checks': [{'name': 'toolset search', 'ok': contract_ok, 'required': True}],
            }
            return subprocess.CompletedProcess(
                argv, 0 if contract_ok else 1, json.dumps(report), ''
            )

        return calls, mock.patch.object(up.subprocess, 'run', side_effect=run)

    def _state(self):
        return json.loads((self.root / 'state.json').read_text(encoding='utf-8'))

    def test_nothing_newer_installs_nothing(self):
        calls, run = self._fake_tools()
        with mock.patch.object(up, 'urlopen', return_value=_github(sha=OLD)), run:
            self.assertEqual(up.update(self._args()), 'current')
        self.assertEqual(calls, [])

    def test_a_newer_commit_that_keeps_the_contract_becomes_the_janus_to_use(self):
        calls, run = self._fake_tools()
        with mock.patch.object(up, 'urlopen', return_value=_github()), run:
            self.assertEqual(up.update(self._args()), 'installed')
        pip = next(c for c in calls if c[0].endswith('/pip'))
        self.assertIn(
            f'janus-agent[mcp] @ https://github.com/magnetoid/Janus-Agent/archive/{NEW}.tar.gz', pip
        )
        self.assertIn('ddgs==9.16.0', pip)
        contract = calls[-1]
        self.assertEqual(contract[1:], ['-I', '/app/core/assistant/janus_contract.py'])
        state = self._state()
        venv = self.root / 'venvs' / NEW[:12]
        self.assertEqual(state['active']['commit'], NEW)
        self.assertEqual(state['active']['bin'], str(venv / 'bin' / 'janus'))
        self.assertEqual(json.loads((venv / 'morpheus-build.json').read_text())['commit'], NEW)
        self.assertTrue((venv / 'morpheus-contract.json').is_file())

    def test_a_commit_that_breaks_the_contract_is_never_used(self):
        _, run = self._fake_tools(contract_ok=False)
        with mock.patch.object(up, 'urlopen', return_value=_github()), run:
            self.assertEqual(up.update(self._args()), 'failed')
        state = self._state()
        self.assertNotIn('active', state)
        self.assertIn('toolset search', state['failed'][NEW]['reason'])
        self.assertFalse((self.root / 'venvs' / NEW[:12]).exists())

    def test_a_failed_install_is_recorded_and_cleaned_up(self):
        _, run = self._fake_tools(pip_rc=1)
        with mock.patch.object(up, 'urlopen', return_value=_github()), run:
            self.assertEqual(up.update(self._args()), 'failed')
        self.assertIn('pip exploded', self._state()['failed'][NEW]['reason'])
        self.assertFalse((self.root / 'venvs' / NEW[:12]).exists())

    def test_a_failed_commit_is_not_retried_until_forced(self):
        (self.root / 'state.json').write_text(json.dumps({'failed': {NEW: {'reason': 'x'}}}))
        calls, run = self._fake_tools()
        with mock.patch.object(up, 'urlopen', side_effect=lambda *a, **k: _github()), run:
            self.assertEqual(up.update(self._args()), 'skipped')
            self.assertEqual(calls, [])
            self.assertEqual(up.update(self._args(force=True)), 'installed')

    def test_github_trouble_is_recorded_not_raised(self):
        with mock.patch.object(up, 'urlopen', side_effect=OSError('offline')):
            self.assertEqual(up.update(self._args()), 'error')
        self.assertIn('offline', self._state()['last_check']['detail'])

    def test_the_replaced_janus_is_kept_for_a_rollback_and_older_ones_go(self):
        for sha in ('a' * 40, 'b' * 40):
            (self.root / 'venvs' / sha[:12]).mkdir(parents=True)
        (self.root / 'state.json').write_text(
            json.dumps(
                {'active': {'commit': 'b' * 40, 'bin': 'x'}, 'previous': {'commit': 'a' * 40}}
            )
        )
        _, run = self._fake_tools()
        with mock.patch.object(up, 'urlopen', return_value=_github()), run:
            up.update(self._args())
        state = self._state()
        self.assertEqual(state['previous']['commit'], 'b' * 40)
        kept = sorted(p.name for p in (self.root / 'venvs').iterdir())
        self.assertEqual(kept, sorted([NEW[:12], 'b' * 12]))

    def test_one_update_at_a_time(self):
        import fcntl

        with (self.root / '.lock').open('a') as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            with mock.patch.object(up, 'update') as run_update:
                self.assertEqual(
                    up.main(
                        [
                            '--engine-dir',
                            str(self.root),
                            '--repo',
                            'magnetoid/Janus-Agent',
                            '--ref',
                            'main',
                            '--contract',
                            'c.py',
                        ]
                    ),
                    0,
                )
            run_update.assert_not_called()

    def test_arguments_are_validated_before_anything_is_fetched(self):
        for bad in (
            ['--repo', 'magnetoid/Janus-Agent; rm -rf /', '--ref', 'main'],
            ['--repo', 'magnetoid/Janus-Agent', '--ref', 'main --upgrade'],
        ):
            with self.assertRaises(SystemExit), mock.patch('sys.stderr'):
                up.main(['--engine-dir', str(self.root), '--contract', 'c.py', *bad])

    def test_it_runs_without_django(self):
        source = Path(up.__file__).read_text(encoding='utf-8')
        self.assertNotIn('django', source)
        self.assertNotIn('from core', source)


class DockerfileTests(SimpleTestCase):
    """The image and the updater install Janus the same way, and both check it."""

    def test_the_build_checks_janus_and_pins_what_the_updater_installs(self):
        import re

        from django.conf import settings

        text = (Path(settings.BASE_DIR) / 'Dockerfile').read_text(encoding='utf-8')
        for pin in rt.PINS:
            self.assertEqual(text.count(pin), 2, pin)  # the install and the fallback
        # The contract file is copied in on its own (so the Janus layer caches
        # across deploys), then run after the install and after the fallback.
        self.assertEqual(text.count('/app/core/assistant/janus_contract.py'), 3)
        # Both refs are reviewed commits (v0.87.4): the build is reproducible
        # and the owner moves Janus by bumping the ARG, not by pushing to main.
        for arg in ('JANUS_REF', 'JANUS_KNOWN_GOOD'):
            found = re.search(rf'ARG {arg}=(\S+)', text)
            self.assertRegex(found.group(1), r'^[0-9a-f]{40}$', arg)
        self.assertIn('ARG JANUS_REPO=https://github.com/magnetoid/Janus-Agent.git', text)
        # The Janus layer runs before the application copy, or every push
        # rebuilds it (216 MB a build, four builds a push).
        self.assertLess(
            text.index('/opt/janus/bin/pip install'),
            text.index('COPY --chown=morpheus:morpheus . /app'),
        )
