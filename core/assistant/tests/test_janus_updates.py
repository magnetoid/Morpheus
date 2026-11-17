"""Janus moves only with a Morpheus release, and every store knows which build it runs.

The image installs the Janus commit the Dockerfile pins and checks it against
Morpheus's contract; a newer Janus arrives by the pull request that moves the pin
(.github/workflows/janus-bump.yml). The store-side self-updater that installed
newer commits at runtime was retired in v0.175.1, so nothing on a running store
chooses another Janus.

pip writes what it resolved into the dist-info's ``direct_url.json``; on prod
(2026-10-09) that read ``{"url": "https://github.com/magnetoid/janus.git",
"vcs_info": {"commit_id": "eafb7ab…", "requested_revision": "main"}}``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from core.assistant import janus_engine as eng
from core.assistant import janus_runtime as rt

OLD = 'eafb7aba34db8645401ce285edf987054c5d37d5'
NEW = '0123456789abcdef0123456789abcdef01234567'


def _venv(root: Path, sha: str, *, url: str | None = None) -> Path:
    """A fake Janus venv: bin/janus plus the dist-info pip would write."""
    dist = root / 'lib' / 'python3.12' / 'site-packages' / 'janus_agent-0.18.0.dist-info'
    dist.mkdir(parents=True)
    (dist / 'METADATA').write_text('Name: janus-agent\nVersion: 0.18.0\n', encoding='utf-8')
    origin = (
        {'url': url, 'archive_info': {}}
        if url
        else {
            'url': 'https://github.com/magnetoid/Janus-Agent.git',
            'vcs_info': {'commit_id': sha, 'requested_revision': OLD, 'vcs': 'git'},
        }
    )
    (dist / 'direct_url.json').write_text(json.dumps(origin), encoding='utf-8')
    (root / 'bin').mkdir()
    janus = root / 'bin' / 'janus'
    janus.write_text('#!/bin/sh\n', encoding='utf-8')
    janus.chmod(0o755)
    return janus


class InstalledBuildTests(SimpleTestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_the_image_build_is_read_from_pips_git_record(self):
        build = rt.installed_build(str(_venv(self.root / 'image', OLD)))
        self.assertEqual(
            (build['version'], build['commit'], build['ref'], build['repo']),
            ('0.18.0', OLD, OLD, 'magnetoid/Janus-Agent'),
        )

    def test_an_install_from_githubs_archive_names_its_commit(self):
        # How a local conformance run installs a pinned commit without git.
        url = f'https://github.com/magnetoid/Janus-Agent/archive/{NEW}.tar.gz'
        build = rt.installed_build(str(_venv(self.root / 'archive', NEW, url=url)))
        self.assertEqual(
            (build['commit'], build['ref'], build['repo']), (NEW, '', 'magnetoid/Janus-Agent')
        )

    def test_nothing_installed_reads_as_unknown(self):
        self.assertEqual(rt.installed_build(None)['commit'], '')
        self.assertEqual(rt.installed_build(str(self.root / 'none' / 'bin' / 'janus'))['repo'], '')

    def test_a_turn_names_the_build_it_runs(self):
        janus = _venv(self.root / 'image', OLD)
        eng._build_of.cache_clear()
        self.addCleanup(eng._build_of.cache_clear)
        self.assertEqual(eng.build_of([str(janus)]), {'version': '0.18.0', 'commit': OLD})
        self.assertEqual(eng.build_of(None), {'version': '', 'commit': ''})

    def test_the_contract_report_is_the_one_the_build_wrote_beside_janus(self):
        janus = _venv(self.root / 'image', OLD)
        report = {'ok': True, 'checks': [{'name': 'toolset search', 'ok': True}]}
        (self.root / 'image' / rt.CONTRACT_FILE).write_text(json.dumps(report), encoding='utf-8')
        self.assertEqual(rt.contract_report(str(janus)), report)
        self.assertEqual(rt.contract_report(None), {})


class EngineBinaryTests(SimpleTestCase):
    """The program a turn runs comes from the deployment, never from a file a turn
    or the dashboard can write."""

    def test_the_engine_runs_the_image_janus(self):
        with (
            override_settings(JANUS_BIN=''),
            mock.patch.object(eng.shutil, 'which', return_value='/usr/local/bin/janus'),
        ):
            self.assertEqual(eng.janus_cmd(), ['/usr/local/bin/janus'])

    def test_an_explicit_janus_bin_wins(self):
        with override_settings(JANUS_BIN='/opt/custom/janus'):
            self.assertEqual(eng.janus_cmd(), ['/opt/custom/janus'])

    def test_state_the_retired_updater_left_in_a_home_chooses_nothing(self):
        # The updater recorded the Janus to run in <home>/engine/state.json, a
        # directory every turn can write. Nothing reads it any more.
        with TemporaryDirectory() as home:
            other = _venv(Path(home) / 'engine' / 'venvs' / NEW[:12], NEW)
            state = {'active': {'commit': NEW, 'bin': str(other)}}
            (Path(home) / 'engine' / 'state.json').write_text(json.dumps(state), encoding='utf-8')
            with (
                override_settings(JANUS_BIN='', LINDA_JANUS_HOME=home),
                mock.patch.object(eng.shutil, 'which', return_value='/usr/local/bin/janus'),
            ):
                self.assertEqual(eng.janus_cmd(), ['/usr/local/bin/janus'])


class DockerfileTests(SimpleTestCase):
    """The image installs the pinned Janus once, with its companion pins, and checks it."""

    def test_the_build_checks_janus_and_installs_the_companion_pins(self):
        text = (Path(settings.BASE_DIR) / 'Dockerfile').read_text(encoding='utf-8')
        for pin in rt.PINS:
            self.assertEqual(text.count(pin), 2, pin)  # the install and the fallback
        # The contract file is copied in on its own (so the Janus layer caches
        # across deploys), then run after the install and after the fallback.
        self.assertEqual(text.count('/app/core/assistant/janus_contract.py'), 3)
        # The page reads the report from beside the venv (contract_report).
        self.assertIn(f'/opt/janus/{rt.CONTRACT_FILE}', text)
        # Both refs are reviewed commits (v0.87.4): the build is reproducible
        # and Janus moves by the pull request that bumps the ARG.
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

    def test_ci_runs_the_conformance_suite_on_the_janus_the_image_pins(self):
        ci = (Path(settings.BASE_DIR) / '.github' / 'workflows' / 'ci.yml').read_text(
            encoding='utf-8'
        )
        job = ci[ci.index('  janus-conformance:') :]
        job = job[: job.index('\n  api-stability:')]
        # The repository, ref and companion pins come from the Dockerfile and
        # janus_runtime.PINS through scripts/bump_janus.py, never a second copy.
        self.assertIn('python3 scripts/bump_janus.py env >> "$GITHUB_ENV"', job)
        self.assertIn('"janus-agent[mcp] @ git+${JANUS_REPO}@${JANUS_REF}" $JANUS_PINS', job)
        for pin in rt.PINS:
            self.assertNotIn(pin, job)
        self.assertNotIn('github.com/magnetoid/Janus-Agent', job)
        self.assertIn('JANUS_CONFORMANCE_BIN: /tmp/janus/bin/janus', job)
        self.assertIn("grep -q 'skipped='", job)
