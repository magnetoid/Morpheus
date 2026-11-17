"""scripts/bump_janus.py and the janus-bump workflow: Janus moves by pull request (P3)."""

from __future__ import annotations

import difflib
import importlib.util
import json
import re
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core.assistant import janus_runtime as rt

_ROOT = Path(settings.BASE_DIR)
_SPEC = importlib.util.spec_from_file_location('bump_janus', _ROOT / 'scripts' / 'bump_janus.py')
bj = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bj)

DOCKERFILE = (_ROOT / 'Dockerfile').read_text(encoding='utf-8')
PINNED = bj.read(DOCKERFILE)['ref']
NEW = 'c' * 40


class ReadTests(SimpleTestCase):
    def test_reads_the_pin_the_image_installs(self):
        pin = bj.read(DOCKERFILE)
        self.assertEqual(pin['repo'], 'https://github.com/magnetoid/Janus-Agent.git')
        self.assertEqual(pin['slug'], 'magnetoid/Janus-Agent')
        self.assertRegex(pin['ref'], r'^[0-9a-f]{40}$')
        self.assertRegex(pin['known_good'], r'^[0-9a-f]{40}$')
        self.assertIn('git+${JANUS_REPO}@${JANUS_REF}', DOCKERFILE)

    def test_companion_pins_are_janus_runtime_pins(self):
        # Read without importing janus_runtime: the workflow runs the script first.
        self.assertEqual(bj.pins(), rt.PINS)

    def test_env_lines_feed_github_env(self):
        lines = bj.env_lines(DOCKERFILE)
        self.assertEqual(
            [line.split('=', 1)[0] for line in lines],
            ['JANUS_REPO', 'JANUS_SLUG', 'JANUS_REF', 'JANUS_KNOWN_GOOD', 'JANUS_PINS'],
        )
        self.assertIn(f'JANUS_PINS={" ".join(rt.PINS)}', lines)
        self.assertIn(f'JANUS_REF={PINNED}', lines)
        for line in lines:
            self.assertNotIn('\n', line)

    def test_refuses_a_dockerfile_it_cannot_read_one_way(self):
        two = DOCKERFILE.replace(
            f'ARG JANUS_REF={PINNED}', f'ARG JANUS_REF={PINNED}\nARG JANUS_REF={NEW}'
        )
        branch = re.sub(r'^ARG JANUS_REF=\S+', 'ARG JANUS_REF=main', DOCKERFILE, flags=re.M)
        elsewhere = DOCKERFILE.replace(
            'ARG JANUS_REPO=https://github.com/magnetoid/Janus-Agent.git',
            'ARG JANUS_REPO=https://example.com/Janus-Agent.git',
        )
        gone = re.sub(r'^ARG JANUS_KNOWN_GOOD=\S+\n', '', DOCKERFILE, flags=re.M)
        for text in (two, branch, elsewhere, gone):
            with (
                self.subTest(text=text[text.find('ARG JANUS') :][:200]),
                self.assertRaises(bj.BumpError),
            ):
                bj.read(text)


class BumpTests(SimpleTestCase):
    def test_pins_the_new_commit_and_keeps_the_old_one_as_fallback(self):
        moved = bj.bump(DOCKERFILE, NEW)
        pin = bj.read(moved)
        self.assertEqual(pin['ref'], NEW)
        self.assertEqual(pin['known_good'], PINNED)
        self.assertEqual(pin['repo'], bj.read(DOCKERFILE)['repo'])
        changed = [
            line
            for line in difflib.unified_diff(DOCKERFILE.splitlines(), moved.splitlines(), n=0)
            if line[:1] in '+-' and not line.startswith(('+++', '---'))
        ]
        # Only the two ARG lines (one when the fallback already named the old pin).
        self.assertTrue(changed)
        self.assertTrue(all(re.match(r'^[+-]ARG JANUS_(REF|KNOWN_GOOD)=', c) for c in changed))

    def test_refuses_what_is_not_a_commit(self):
        for sha in ('main', 'C' * 40, 'c' * 39, 'c' * 41, f'{NEW}\n', '', f'{NEW[:-1]}g'):
            with self.subTest(sha=sha), self.assertRaises(bj.BumpError):
                bj.bump(DOCKERFILE, sha)

    def test_refuses_the_commit_already_pinned(self):
        with self.assertRaises(bj.BumpError):
            bj.bump(DOCKERFILE, PINNED)

    def test_the_command_writes_the_dockerfile_or_leaves_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'Dockerfile'
            path.write_text(DOCKERFILE, encoding='utf-8')
            self.assertEqual(bj.main(['--dockerfile', str(path), 'bump', 'main']), 1)
            self.assertEqual(path.read_text(encoding='utf-8'), DOCKERFILE)
            self.assertEqual(bj.main(['--dockerfile', str(path), 'bump', NEW]), 0)
            self.assertEqual(bj.read(path.read_text(encoding='utf-8'))['ref'], NEW)


def _check(name, ok=True, required=True, detail=''):
    return {'name': name, 'ok': ok, 'required': required, 'detail': detail}


class BodyTests(SimpleTestCase):
    _FILES = {
        'compare': 'compare.json',
        'contract_pinned': 'contract-pinned.json',
        'contract_new': 'contract-new.json',
        'log': 'conformance.txt',
        'offered': 'conformance.json',
        'audit': 'audit.txt',
    }

    def _write(self, tmp: Path, **files):
        for key, value in files.items():
            text = value if isinstance(value, str) else json.dumps(value)
            (tmp / self._FILES[key]).write_text(text, encoding='utf-8')

    def _body(self, tmp: Path) -> str:
        return bj.body(
            pinned=PINNED,
            new=NEW,
            slug='magnetoid/Janus-Agent',
            directory=tmp,
            run_url='https://r/1',
        )

    def test_names_the_range_and_only_what_changed(self):
        compare = {
            'ahead_by': 3,
            'commits': [
                {'sha': 'a' * 40, 'commit': {'message': 'feat: one\n\nlong body'}},
                {'sha': 'b' * 40, 'commit': {'message': 'fix(`x`): ping @someone about #12'}},
                {'sha': 'd' * 40, 'commit': {'message': 'chore: three'}},
            ],
            'files': [
                {'filename': 'cli.py'},
                {'filename': 'agent/loop.py'},
                {'filename': 'docs/a.md'},
            ],
        }
        pinned = {
            'ok': True,
            'version': '0.18.0',
            'commit': PINNED,
            'checks': [
                _check('config a'),
                _check('config b'),
                _check('hint', ok=False, required=False),
            ],
            'notes': ['old note'],
        }
        new = {
            'ok': False,
            'version': '0.19.0',
            'commit': NEW,
            'checks': [
                _check('config a'),
                _check('config b', ok=False, detail='gone from cli.py'),
                _check('hint', ok=True, required=False),
                _check('config c'),
            ],
            'notes': ['new note'],
        }
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            self._write(
                tmp,
                compare=compare,
                contract_pinned=pinned,
                contract_new=new,
                log='test_a ... ok\n\nRan 7 tests in 140.2s\n\nOK\n',
                offered={'tools_offered': 249, 'tool_schema_bytes': 139510},
                audit='No known vulnerabilities found\n',
            )
            text = self._body(tmp)
        self.assertIn(f'https://github.com/magnetoid/Janus-Agent/compare/{PINNED}...{NEW}', text)
        self.assertIn('3 commits on magnetoid/Janus-Agent', text)
        self.assertIn('| `config b` | required | ok | fails | `gone from cli.py` |', text)
        self.assertIn('| `hint` | reported | fails | ok |', text)
        self.assertIn('| `config c` | required | new check | ok |', text)
        self.assertNotIn('`config a`', text)
        self.assertIn('- added: `new note`', text)
        self.assertIn('- gone: `old note`', text)
        self.assertIn('| result | passes | fails |', text)
        self.assertIn('Ran 7 tests in 140 s: OK.', text)
        self.assertIn('"tools_offered": 249', text)
        self.assertIn('No known vulnerabilities found', text)
        self.assertIn('Files changed: 3; in the files the contract reads: 2.', text)
        # Upstream text sits in a fenced block: no @mention, no #reference, no
        # backtick that closes the fence.
        commits = text[text.index('### Commits') :]
        start = commits.index('```text\n') + len('```text\n')
        block = commits[start : commits.index('\n```', start)]
        self.assertIn(f"{'b' * 12}  fix('x'): ping @someone about #12", block)
        self.assertIn(f'{"a" * 12}  feat: one', block)
        self.assertNotIn('long body', text)
        self.assertEqual(text.count('```') % 2, 0)

    def test_a_step_that_did_not_run_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self._body(Path(tmp))
        self.assertIn('Some commits on', text)
        self.assertIn('The contract did not run on the candidate.', text)
        self.assertIn('The conformance suite did not run on the candidate.', text)
        self.assertIn('pip-audit did not run.', text)
        self.assertIn('The compare call failed', text)

    def test_failing_tests_are_named(self):
        log = (
            'FAIL: test_empty_reply_is_an_error '
            '(core.assistant.tests.conformance.test_janus_conformance.JanusConformanceTests'
            '.test_empty_reply_is_an_error)\n'
            'ERROR: test_memory (core.assistant.tests.conformance.x.T.test_memory)\n'
            '\nRan 7 tests in 90.0s\n\nFAILED (failures=1, errors=1)\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            self._write(tmp, log=log)
            text = self._body(tmp)
        self.assertIn('Ran 7 tests in 90 s: FAILED (failures=1, errors=1).', text)
        self.assertIn('- `test_empty_reply_is_an_error (core.assistant', text)
        self.assertIn('- `test_memory (core.assistant.tests.conformance.x.T.test_memory)`', text)

    def test_fits_a_pull_request_description(self):
        compare = {
            'ahead_by': 300,
            'commits': [{'sha': f'{i:040x}', 'commit': {'message': 'x' * 400}} for i in range(300)],
            'files': [{'filename': f'agent/f{i}.py'} for i in range(3000)],
        }
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            self._write(
                tmp, compare=compare, audit='\n'.join(f'pkg{i} 1.0 GHSA-x' for i in range(9000))
            )
            text = self._body(tmp)
        self.assertLessEqual(len(text), bj.BODY_LIMIT + 100)
        self.assertLess(len(text), 65_536)
        self.assertEqual(text.count('```') % 2, 0)
        self.assertIn('Commits (100 of 300)', text)

    def test_title(self):
        self.assertEqual(
            bj.title(PINNED, NEW, {'ahead_by': 3}), f'Janus: move the pin to {NEW[:12]} (3 commits)'
        )
        self.assertEqual(
            bj.title(PINNED, NEW, {'ahead_by': 1}), f'Janus: move the pin to {NEW[:12]} (1 commit)'
        )
        self.assertEqual(bj.title(PINNED, NEW, None), f'Janus: move the pin to {NEW[:12]}')


class WorkflowTests(SimpleTestCase):
    """What the bump workflow may do, read from its text (no YAML parser in the lock)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.text = (_ROOT / '.github' / 'workflows' / 'janus-bump.yml').read_text(encoding='utf-8')
        cls.jobs = {}
        names = re.findall(r'^  ([a-z-]+):\n', cls.text[cls.text.index('\njobs:') :], re.M)
        body = cls.text[cls.text.index('\njobs:') :]
        for i, name in enumerate(names):
            start = body.index(f'\n  {name}:\n')
            end = body.index(f'\n  {names[i + 1]}:\n') if i + 1 < len(names) else len(body)
            cls.jobs[name] = body[start:end]

    def test_no_job_merges_or_runs_with_the_base_branch_token(self):
        self.assertIn('\npermissions: {}\n', self.text)
        for banned in (
            'pull_request_target',
            'gh pr merge',
            '--auto',
            'auto-merge',
            'gh pr review',
        ):
            self.assertNotIn(banned, self.text)
        self.assertEqual(set(self.jobs), {'resolve', 'candidate', 'pull-request'})

    def test_only_the_job_that_runs_no_janus_can_write(self):
        for name in ('resolve', 'candidate'):
            job = self.jobs[name]
            self.assertIn('      contents: read\n', job, name)
            self.assertNotRegex(job, r':\s*write\b', name)
            self.assertIn('persist-credentials: false', job, name)
        job = self.jobs['pull-request']
        self.assertIn('      contents: write\n      pull-requests: write\n', job)
        self.assertIn(
            "if: github.event_name != 'pull_request' && needs.candidate.outputs.move == 'true'", job
        )
        self.assertNotIn('/tmp/janus/bin', job)
        self.assertIn('gh pr create --draft --base main', job)

    def test_the_repository_comes_from_the_dockerfile(self):
        inputs = self.text[self.text.index('    inputs:\n') : self.text.index('  pull_request:\n')]
        self.assertEqual(re.findall(r'^      ([a-z_]+):\n', inputs, re.M), ['commit'])
        self.assertIn('python3 scripts/bump_janus.py env >> "$GITHUB_ENV"', self.jobs['resolve'])
        self.assertIn('git ls-remote "$JANUS_REPO" refs/heads/main', self.jobs['resolve'])
        self.assertIn('=~ ^[0-9a-f]{40}$', self.jobs['resolve'])
        self.assertIn('compare/${new}...main', self.jobs['resolve'])
        self.assertNotIn('github.com/magnetoid', self.text)
        # Inputs and outputs reach a shell only through env, never inline.
        for line in self.text.splitlines():
            if '${{ inputs.' in line or '.outputs.title }}' in line:
                self.assertRegex(line, r'^\s+(?!run:)[A-Za-z_-]+: \$\{\{ ', line)

    def test_the_candidate_is_tested_in_the_same_run(self):
        job = self.jobs['candidate']
        self.assertIn('"janus-agent[mcp] @ git+${JANUS_REPO}@${NEW}" $JANUS_PINS', job)
        self.assertIn('core/assistant/janus_contract.py > /tmp/bump/contract-new.json', job)
        self.assertIn('manage.py test core.assistant.tests.conformance', job)
        self.assertIn("grep -q 'skipped='", job)
        self.assertIn('pip-audit --local', job)
        self.assertLess(job.index('tests.conformance'), job.index('pip-audit --local'))
        self.assertIn('if [ "$EVENT" = pull_request ]', job)

    def test_a_branch_a_person_pushed_to_is_left_alone(self):
        job = self.jobs['pull-request']
        self.assertIn("bot='41898282+github-actions[bot]@users.noreply.github.com'", job)
        self.assertIn('grep -vxF "$bot"', job)
        self.assertIn('--force-with-lease="refs/heads/${BRANCH}:${observed}"', job)
        self.assertIn('python3 scripts/bump_janus.py bump "$NEW"', job)
        # grep -q under pipefail would read a match as a miss.
        commit_step = job[
            job.index('- name: Commit the new pin') : job.index('- name: Open or update')
        ]
        self.assertNotIn('grep -q', commit_step.replace('# No `grep -q`', ''))
