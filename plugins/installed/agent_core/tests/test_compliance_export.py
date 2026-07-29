"""EU AI Act evidence export — permission boundary + content.

The report page is staff-only, and the CSV/report must actually contain the
recorded AI decisions + approvals so a merchant can hand it to a regulator.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

URL = '/dashboard/apps/agent_core/compliance/'


def _seed_decision():
    from morpheus.core import record_ai_decision

    record_ai_decision(
        agent='worker',
        tool='orders.refund',
        run_id='run-1',
        args={'order_number': 'O-9'},
        output={'ok': True},
        model='claude-opus-4-8',
        provider='anthropic',
        target='order/O-9',
    )


class AiActReportBoundaryTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='compl-staff', email='compl@x.test', password='pw', is_staff=True
        )

    def test_anonymous_is_redirected(self):
        self.assertEqual(Client().get(URL).status_code, 302)

    def test_staff_can_view(self):
        c = Client()
        c.force_login(self.staff)
        self.assertEqual(c.get(URL).status_code, 200)


class AiActReportContentTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='compl-staff2', email='compl2@x.test', password='pw', is_staff=True
        )
        _seed_decision()

    def test_report_service_captures_the_decision(self):
        from plugins.installed.agent_core.compliance import build_ai_act_report

        r = build_ai_act_report()
        self.assertEqual(r['summary']['total_decisions'], 1)
        d = r['decisions'][0]
        self.assertEqual(d['tool'], 'orders.refund')
        self.assertEqual(d['target'], 'order/O-9')
        self.assertEqual(d['model'], 'claude-opus-4-8')

    def test_csv_export_contains_the_decision(self):
        c = Client()
        c.force_login(self.staff)
        resp = c.get(URL, {'export': 'csv', 'days': 30})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        body = resp.content.decode()
        self.assertIn('orders.refund', body)
        self.assertIn('order/O-9', body)

    def test_management_command_runs(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command('export_ai_act_report', '--days', '30', '--format', 'csv', stdout=out)
        self.assertIn('orders.refund', out.getvalue())

    def test_window_excludes_old_decisions(self):
        # A decision timestamped before the window must not appear.
        from datetime import timedelta

        from core.audit.models import AuditEvent
        from plugins.installed.agent_core.compliance import build_ai_act_report

        old = timezone.now() - timedelta(days=400)
        AuditEvent.objects.all().update(created_at=old)
        r = build_ai_act_report(since=timezone.now() - timedelta(days=30), until=timezone.now())
        self.assertEqual(r['summary']['total_decisions'], 0)
