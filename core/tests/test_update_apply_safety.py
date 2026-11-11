"""apply_platform_update crash-safety gates: dependency guard + fresh-interpreter
boot-probe (before migrate, so a non-bootable update reverts with DB untouched)."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest import mock
from unittest.mock import patch

from django.test import TestCase, override_settings

from core import updates
from core.signing import generate_keypair, sign_manifest

STATUS_BEHIND = {
    'source': 'git',
    'available': 'yes',
    'upstream': 'origin/main',
    'current': 'v0.2.11',
    'latest': 'v0.2.12',
    'behind': 1,
}


@override_settings(MORPHEUS_SELF_UPDATE_ENABLED=True)
class ApplySafetyTests(TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        (root / '.git').mkdir()
        self.root = root
        self._stack = [
            patch('core.updates._repo_root', return_value=root),
            patch('core.updates.platform_update_status', return_value=dict(STATUS_BEHIND)),
            patch('core.updates._git', return_value='abc1234'),
            patch('core.updates._git_ok', return_value=True),
        ]
        for p in self._stack:
            p.start()

    def tearDown(self):
        for p in self._stack:
            p.stop()
        self._tmp.cleanup()

    def test_dependency_change_refuses_before_any_mutation(self):
        with (
            patch('core.updates._dependency_changes', return_value=['requirements.txt']),
            patch('django.core.management.call_command') as cc,
            patch('core.updates._boot_probe') as probe,
        ):
            out = updates.apply_platform_update(confirm=True)
        self.assertEqual(out['status'], 'deps_changed')
        self.assertFalse(out['ok'])
        self.assertIn('requirements.txt', out['plan']['dependency_files'])
        cc.assert_not_called()  # no backup / merge / migrate
        probe.assert_not_called()

    def test_dependency_change_allowed_proceeds(self):
        with (
            patch('core.updates._dependency_changes', return_value=['requirements.txt']),
            patch('django.core.management.call_command'),
            patch('core.updates._boot_probe', return_value=(True, '')),
        ):
            out = updates.apply_platform_update(confirm=True, allow_dependency_changes=True)
        self.assertEqual(out['status'], 'applied')

    def test_boot_probe_failure_rolls_back_before_migrate(self):
        with (
            patch('core.updates._dependency_changes', return_value=[]),
            patch(
                'core.updates._boot_probe', return_value=(False, 'ImportError: no module xmlsec')
            ),
            patch('django.core.management.call_command') as cc,
        ):
            out = updates.apply_platform_update(confirm=True)
        self.assertEqual(out['status'], 'rolled_back')
        self.assertIn('failed to boot', out['reason'])
        # backup ran, but migrate must NOT have (probe gate is before migrate)
        called = [c.args[0] for c in cc.call_args_list]
        self.assertIn('morph_backup', called)
        self.assertNotIn('migrate', called)

    def test_happy_path_applies(self):
        with (
            patch('core.updates._dependency_changes', return_value=[]),
            patch('core.updates._boot_probe', return_value=(True, '')),
            patch('django.core.management.call_command') as cc,
        ):
            out = updates.apply_platform_update(confirm=True)
        self.assertEqual(out['status'], 'applied')
        called = [c.args[0] for c in cc.call_args_list]
        self.assertIn('migrate', called)
        self.assertIn('check', called)


def _run(args, cwd):
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True)


def _commit(repo, name, files=None):
    for path, text in (files or {name: name}).items():
        (Path(repo) / path).write_text(text)
    _run(['add', '-A'], repo)
    _run(['commit', '-q', '-m', name], repo)
    return _run(['rev-parse', 'HEAD'], repo).stdout.strip()


@override_settings(MORPHEUS_SELF_UPDATE_ENABLED=True)
class ApplyToManifestCommitTests(TestCase):
    """Real git repos: a bare origin holding A -> B -> C, a checkout sitting at A."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        self.origin = base / 'origin.git'
        self.work = base / 'work'
        self.pusher = base / 'pusher'
        _run(['init', '-q', '--bare', '-b', 'main', str(self.origin)], base)
        _run(['clone', '-q', str(self.origin), str(self.pusher)], base)
        _run(['config', 'user.name', 'T'], self.pusher)
        _run(['config', 'user.email', 't@example.test'], self.pusher)
        self.a = _commit(self.pusher, 'a')
        _run(['push', '-q', 'origin', 'main'], self.pusher)
        _run(['clone', '-q', str(self.origin), str(self.work)], base)
        _run(['config', 'user.name', 'T'], self.work)
        _run(['config', 'user.email', 't@example.test'], self.work)
        patches = [
            patch('core.updates._repo_root', return_value=self.work),
            patch('core.updates._boot_probe', return_value=(True, '')),
            patch('django.core.management.call_command'),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _push_more(self, files_b=None):
        self.b = _commit(self.pusher, 'b', files_b)
        self.c = _commit(self.pusher, 'c')
        _run(['push', '-q', 'origin', 'main'], self.pusher)

    def _head(self):
        return _run(['rev-parse', 'HEAD'], self.work).stdout.strip()

    def _channel(self, commit):
        return {
            'source': 'manifest',
            'available': 'yes',
            'current': 'v0.2.11',
            'latest': 'v0.2.12',
            'commit': commit,
            'path': 'git',
        }

    def _apply(self, commit):
        with patch('core.updates.platform_update_status', return_value=self._channel(commit)):
            return updates.apply_platform_update(confirm=True)

    def test_moves_to_the_manifest_commit_only(self):
        self._push_more()
        out = self._apply(self.b)
        self.assertEqual(out['status'], 'applied')
        self.assertEqual(out['plan']['target'], self.b)
        self.assertEqual(self._head(), self.b)
        self.assertNotEqual(self._head(), self.c)

    def test_refuses_a_commit_that_is_not_a_descendant(self):
        _run(['checkout', '-q', '-b', 'side'], self.pusher)
        side = _commit(self.pusher, 'side')
        _run(['push', '-q', 'origin', 'side'], self.pusher)
        _run(['checkout', '-q', 'main'], self.pusher)
        self._push_more()
        # The checkout moves to C, so the side commit is no descendant of HEAD.
        _run(['pull', '-q', '--ff-only', 'origin', 'main'], self.work)
        out = self._apply(side)
        self.assertEqual(out['status'], 'diverged')
        self.assertIn('Update by hand', out['reason'])
        self.assertEqual(self._head(), self.c)

    def test_still_refuses_dependency_changes(self):
        self._push_more({'requirements.txt': 'django\n'})
        out = self._apply(self.b)
        self.assertEqual(out['status'], 'deps_changed')
        self.assertEqual(self._head(), self.a)

    def test_a_release_without_a_commit_is_refused(self):
        out = self._apply('')
        self.assertEqual(out['status'], 'no_commit')
        self.assertEqual(out['reason'], 'The release names no commit to update to.')

    def test_a_target_that_is_not_a_commit_id_is_refused(self):
        self._push_more()
        for target in ('main', '--upload-pack=x', 'A' * 40):
            with (
                self.subTest(target=target),
                patch('core.updates._git', wraps=updates._git) as git,
            ):
                out = self._apply(target)
                self.assertEqual(out['status'], 'no_commit')
                self.assertEqual(self._head(), self.a)
                self.assertFalse([c for c in git.call_args_list if c.args[0][0] == 'fetch'])

    def test_an_unfetchable_commit_is_apply_failed(self):
        out = self._apply('f' * 40)
        self.assertEqual(out['status'], 'apply_failed')
        self.assertIn("could not fetch the release's commit", out['reason'].lower())
        self.assertEqual(self._head(), self.a)

    def test_dry_run_fetches_nothing(self):
        self._push_more()
        with (
            patch('core.updates.platform_update_status', return_value=self._channel(self.b)),
            patch('core.updates._git', wraps=updates._git) as git,
        ):
            out = updates.apply_platform_update(confirm=False)
        self.assertEqual(out['status'], 'dry_run')
        self.assertEqual(out['plan']['target'], self.b)
        self.assertFalse([c for c in git.call_args_list if c.args[0][0] == 'fetch'])

    def test_store_ahead_of_the_channel_is_a_noop(self):
        private, public = generate_keypair()
        doc = sign_manifest({'channel': 'stable', 'core': _core_entry(self.a)}, private)
        resp = mock.MagicMock()
        resp.__enter__.return_value.read.return_value = json.dumps(doc).encode()
        with (
            override_settings(
                MORPHEUS_UPDATE_MANIFEST_URL='https://updates.example.test/stable.json',
                MORPHEUS_UPDATE_PUBLIC_KEY=public,
                MORPHEUS_VERSION='v99.0.0',
            ),
            patch('core.update_sources.urllib.request.urlopen', return_value=resp),
            patch('core.updates._git', wraps=updates._git) as git,
        ):
            out = updates.apply_platform_update(confirm=True)
        self.assertEqual(out['status'], 'noop')
        self.assertFalse([c for c in git.call_args_list if c.args[0][0] == 'fetch'])
        self.assertEqual(self._head(), self.a)

    def test_git_checkout_without_the_tool_cannot_update(self):
        with patch('core.updates.can_self_update', return_value=False):
            out = updates.apply_platform_update(confirm=True)
        self.assertEqual(out['status'], 'unavailable')
        self.assertIn('git is not installed', out['reason'])


def _core_entry(commit):
    return {
        'version': 'v0.2.12',
        'commit': commit,
        'image': 'ghcr.io/magnetoid/morpheus:' + commit + '@sha256:' + 'd' * 64,
        'notes': 'Notes',
        'notes_url': 'https://github.com/magnetoid/Morpheus/releases/tag/v0.2.12',
        'breaking': False,
    }


@override_settings(MORPHEUS_SELF_UPDATE_ENABLED=True)
class ApplyOffAndMergeTests(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / '.git').mkdir()
        for p in (
            patch('core.updates._repo_root', return_value=self.root),
            patch('core.updates.shutil.which', return_value='/usr/bin/git'),
        ):
            p.start()
            self.addCleanup(p.stop)

    def test_off_refuses_and_runs_no_git(self):
        with (
            override_settings(MORPHEUS_UPDATE_MANIFEST_URL='off'),
            patch('core.updates._git') as git,
            patch('core.updates._git_ok') as git_ok,
            patch('core.updates.subprocess.run') as run,
        ):
            out = updates.apply_platform_update(confirm=True)
        self.assertFalse(out['ok'])
        self.assertIn('switched off', out['reason'])
        git.assert_not_called()
        git_ok.assert_not_called()
        run.assert_not_called()

    def _merge_fails(self, heads):
        status = {
            'source': 'manifest',
            'available': 'yes',
            'current': 'v1',
            'latest': 'v2',
            'commit': 'a' * 40,
            'path': 'git',
        }
        calls = []

        def git_ok(args, cwd, timeout=10):
            calls.append((args[0], timeout))
            return args[0] != 'merge'

        with (
            patch('core.updates.platform_update_status', return_value=status),
            patch('core.updates._git', side_effect=['b' * 40, *heads]),
            patch('core.updates._git_ok', side_effect=git_ok),
            patch('core.updates._dependency_changes', return_value=[]),
            patch('django.core.management.call_command'),
        ):
            out = updates.apply_platform_update(confirm=True)
        return out, calls

    def test_merge_gets_a_long_timeout_and_unchanged_head_says_so(self):
        out, calls = self._merge_fails(['b' * 40, 'b' * 40])  # fetch, then HEAD again
        self.assertIn(('merge', 120), calls)
        self.assertEqual(out['status'], 'apply_failed')
        self.assertIn('working tree unchanged', out['reason'])

    def test_merge_failure_with_a_moved_head_reports_it(self):
        out, _ = self._merge_fails(['b' * 40, 'c' * 40])
        self.assertNotIn('unchanged', out['reason'])
        self.assertIn('ccccccc', out['reason'])
        self.assertIn('by hand', out['reason'])
