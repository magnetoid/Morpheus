"""Phase 4 apply-engine tests (ADR 0014). Verifies the gates hold and that a
clean, owner-approved proposal lands ONLY on a selfdev/* branch — never main,
never the live working tree. The happy path runs git against a throwaway repo
(REPO_ROOT patched) so it never touches the real checkout.
"""

# Test git invocations use fixed args (no shell); their return codes are asserted
# via the resulting refs/trees, so explicit check= is noise here.
# ruff: noqa: S603, S607, PLW1510
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.assistant import apply as apply_mod
from core.assistant.models import CodeProposal

CLEAN_TOOL_SOURCE = """from core.assistant.tools.filesystem import ToolResult, tool


@tool(
    name="demo-echo",
    description="Echo a message back.",
    schema={"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]},
    scopes=["system.read"],
)
def demo_echo_tool(*, message: str) -> ToolResult:
    return ToolResult(output={"echo": message}, display=message)
"""

_ENABLED = {'MORPHEUS_SELF_UPDATE_ENABLED': '1'}
_DISABLED = {'MORPHEUS_SELF_UPDATE_ENABLED': ''}


def _make_proposal(**kw):
    defaults = {
        'name': 'demo-echo',
        'kind': 'tool',
        'source': CLEAN_TOOL_SOURCE,
        'target_path': 'plugins/installed/linda_generated/tools/demo_echo.py',
        'status': 'approved',
        'passed': True,
        'consensus': {'decision': 'approved', 'providers': 3, 'approvals': 3},
    }
    defaults.update(kw)
    return CodeProposal.objects.create(**defaults)


class ApproveTests(TestCase):
    def test_only_superuser_can_approve(self):
        User = get_user_model()
        staff = User.objects.create_user(username='staff', password='x', is_staff=True)
        owner = User.objects.create_superuser(username='owner', email='o@x.com', password='x')
        p = _make_proposal(status='draft', passed=True)

        with self.assertRaises(PermissionError):
            p.approve(staff)
        p.refresh_from_db()
        self.assertEqual(p.status, 'draft')

        p.approve(owner)
        p.refresh_from_db()
        self.assertEqual(p.status, 'approved')
        self.assertEqual(p.approver, 'o@x.com')
        self.assertIsNotNone(p.approved_at)


class DormantTests(TestCase):
    @mock.patch.dict(os.environ, _DISABLED)
    def test_apply_is_dormant_by_default(self):
        p = _make_proposal()
        result = apply_mod.apply_proposal(p)
        self.assertFalse(result['applied'])
        self.assertIn('disabled', result['reason'])
        p.refresh_from_db()
        self.assertEqual(p.status, 'approved')  # unchanged — nothing applied
        self.assertEqual(p.applied_branch, '')


class PreflightGateTests(TestCase):
    @mock.patch.dict(os.environ, _ENABLED)
    def test_unapproved_rejected(self):
        p = _make_proposal(status='draft')
        self.assertIn('not owner-approved', '; '.join(apply_mod.preflight(p)))

    @mock.patch.dict(os.environ, _ENABLED)
    def test_protected_path_rejected(self):
        p = _make_proposal(target_path='plugins/installed/payments/evil.py')
        self.assertIn('protected path', '; '.join(apply_mod.preflight(p)))

    @mock.patch.dict(os.environ, _ENABLED)
    def test_core_path_rejected(self):
        p = _make_proposal(target_path='core/assistant/tools/generated/x.py')
        self.assertIn('outside', '; '.join(apply_mod.preflight(p)))

    @mock.patch.dict(os.environ, _ENABLED)
    def test_dangerous_source_rejected(self):
        p = _make_proposal(source='import os\nos.system("rm -rf /")\n', passed=False)
        reasons = '; '.join(apply_mod.preflight(p))
        self.assertIn('scan', reasons)

    @mock.patch.dict(os.environ, _ENABLED)
    def test_consensus_required(self):
        p = _make_proposal(consensus={'decision': 'insufficient'})
        self.assertIn('consensus', '; '.join(apply_mod.preflight(p)))

    @mock.patch.dict(os.environ, _ENABLED)
    def test_circuit_breaker(self):
        for i in range(apply_mod.MAX_APPLIES_PER_DAY):
            CodeProposal.objects.create(
                name=f'used-{i}',
                source='x',
                status='applied',
                applied_at=timezone.now(),
            )
        p = _make_proposal()
        self.assertIn('rate limit', '; '.join(apply_mod.preflight(p)))


class ApplyHappyPathTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='selfdev-test-')
        self.root = Path(self.tmp)
        env = {
            **os.environ,
            'GIT_AUTHOR_NAME': 't',
            'GIT_AUTHOR_EMAIL': 't@t',
            'GIT_COMMITTER_NAME': 't',
            'GIT_COMMITTER_EMAIL': 't@t',
        }

        def git(*a):
            subprocess.run(
                ['git', *a], cwd=self.root, check=True, capture_output=True, text=True, env=env
            )

        git('init', '-q')
        (self.root / 'README.md').write_text('seed\n')
        git('add', '.')
        git('commit', '-q', '-m', 'seed')
        git('branch', '-M', 'main')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ls(self, ref):
        return subprocess.run(
            ['git', 'ls-tree', '-r', '--name-only', ref],
            cwd=self.root,
            capture_output=True,
            text=True,
        ).stdout

    @mock.patch.dict(os.environ, _ENABLED)
    def test_apply_lands_on_branch_never_main(self):
        p = _make_proposal()
        with mock.patch.object(apply_mod, 'REPO_ROOT', self.root):
            result = apply_mod.apply_proposal(p)

        self.assertTrue(result['applied'], result)
        branch = result['branch']
        self.assertTrue(branch.startswith('selfdev/'), branch)

        # HEAD is still main and main has NO generated file.
        head = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=self.root,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(head, 'main')
        self.assertNotIn('linda_generated', self._ls('main'))

        # The branch DOES carry the file at the expected path.
        self.assertIn('plugins/installed/linda_generated/tools/demo_echo.py', self._ls(branch))

        # The live working tree is pristine (plumbing wrote nothing to it).
        status = subprocess.run(
            ['git', 'status', '--porcelain'], cwd=self.root, capture_output=True, text=True
        ).stdout
        self.assertEqual(status.strip(), '')

        p.refresh_from_db()
        self.assertEqual(p.status, 'applied')
        self.assertEqual(p.applied_branch, branch)
        self.assertIsNotNone(p.applied_at)
