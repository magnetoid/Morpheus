"""Self-development approval dashboard — RBAC + gate preservation.

Read views are staff-only; approve/apply/reject/revert are superuser-only; and
apply stays blocked while MORPHEUS_SELF_UPDATE_ENABLED is unset (the dashboard
widens no gate).
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

LIST_URL = '/dashboard/agents/selfdev/'


def _proposal(**kw):
    from core.assistant.models import CodeProposal

    defaults = {
        'name': 'demo_tool',
        'kind': 'tool',
        'source': 'def demo():\n    return 1\n',
        'target_path': 'plugins/installed/linda_generated/tools/demo_tool.py',
        'status': 'draft',
        'passed': True,
        'consensus': {'decision': 'approved', 'verdicts': []},
    }
    defaults.update(kw)
    return CodeProposal.objects.create(**defaults)


class SelfdevDashboardRbacTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.staff = U.objects.create_user(
            username='staff', email='s@x.test', password='pw', is_staff=True
        )
        self.owner = U.objects.create_user(
            username='owner', email='o@x.test', password='pw', is_staff=True, is_superuser=True
        )
        self.p = _proposal()

    def _detail(self, p=None):
        return f'/dashboard/agents/selfdev/{(p or self.p).id}/'

    def _action(self, action, p=None):
        return f'/dashboard/agents/selfdev/{(p or self.p).id}/{action}/'

    # ── Read views: staff-only ──────────────────────────────────────────────
    def test_list_redirects_anonymous(self):
        self.assertEqual(Client().get(LIST_URL).status_code, 302)

    def test_list_renders_for_staff(self):
        c = Client()
        c.force_login(self.staff)
        r = c.get(LIST_URL)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'demo_tool')

    def test_detail_renders_for_staff(self):
        c = Client()
        c.force_login(self.staff)
        self.assertEqual(c.get(self._detail()).status_code, 200)

    # ── Mutating actions: superuser-only ────────────────────────────────────
    def test_approve_forbidden_for_non_superuser(self):
        c = Client()
        c.force_login(self.staff)
        r = c.post(self._action('approve'))
        self.assertEqual(r.status_code, 403)
        self.p.refresh_from_db()
        self.assertEqual(self.p.status, 'draft')  # unchanged

    def test_superuser_can_approve(self):
        c = Client()
        c.force_login(self.owner)
        r = c.post(self._action('approve'))
        self.assertEqual(r.status_code, 302)
        self.p.refresh_from_db()
        self.assertEqual(self.p.status, 'approved')
        self.assertTrue(self.p.approver)

    def test_consensus_action_allowed_for_staff(self):
        # Advisory — no privilege change, so staff (non-superuser) may run it.
        c = Client()
        c.force_login(self.staff)
        r = c.post(self._action('consensus'))
        self.assertEqual(r.status_code, 302)

    # ── Apply stays gated by the env master-switch ──────────────────────────
    def test_apply_blocked_when_flag_unset(self):
        p = _proposal(name='approved_tool', status='approved')
        c = Client()
        c.force_login(self.owner)
        r = c.post(self._action('apply', p))
        self.assertEqual(r.status_code, 302)  # redirects back with a message
        p.refresh_from_db()
        self.assertEqual(p.status, 'approved')  # NOT applied — flag is off
