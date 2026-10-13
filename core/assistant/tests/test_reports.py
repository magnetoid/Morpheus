"""Janus's technical reports on Morpheus's own code (docs/plans/janus-core-brain-2026-10.md, C).

Janus files a report in words (what is wrong, how it was or could be fixed), never
code. A superuser reviews it and may send it on, which opens GitHub's new-issue form
in their own browser: the store holds no token and nothing leaves without a person.
"""

from __future__ import annotations

import json
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase

from core.assistant import reports, turn_identity
from core.assistant.models import CodeProposal
from core.assistant.persistence import StoredMessage, get_default_store

CONV = 'user:reports-test:chat:a'
REPORTS = '/dashboard/agents/reports/'


def _report(**kw):
    fields = {'title': 'Export 500s on empty stores', 'problem': 'The CSV export divides by zero.'}
    fields.update(kw)
    return CodeProposal.objects.create(**fields)


class FilingTests(TestCase):
    """Janus files through the same MCP edge as every other tool."""

    def setUp(self):
        from core.assistant.tools.reports import reports_file_tool

        cache.clear()
        self.user = get_user_model().objects.create_user(
            username='owner', email='owner@example.com', password='x', is_staff=True
        )
        patcher = mock.patch(
            'plugins.installed.agent_mcp.linda_turn._all_tools',
            side_effect=lambda: [reports_file_tool],
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        get_default_store().append(
            conversation_key=CONV,
            message=StoredMessage(role='user', content='why does export fail?'),
        )

    def _call(self, args):
        token = turn_identity.mint(
            user=self.user, conversation_key=CONV, mode_slug='general', ttl_s=85
        )
        body = json.dumps(
            {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'tools/call',
                'params': {'name': 'reports.file', 'arguments': args},
            }
        )
        resp = (
            Client()
            .post(
                '/mcp/admin/v1/',
                data=body,
                content_type='application/json',
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            .json()
        )
        return resp['result']

    def test_filing_needs_no_yes_and_records_who_and_where(self):
        result = self._call(
            {
                'title': 'Export 500s on empty stores',
                'problem': 'The CSV export divides by zero when there are no orders.',
                'fix': 'Return an empty file when the order count is zero.',
                'area': 'orders/export.py',
            }
        )
        self.assertFalse(result.get('isError'), result)
        report = CodeProposal.objects.get()
        self.assertEqual(report.status, 'new')
        self.assertEqual(report.reported_by, self.user)
        self.assertEqual(report.conversation_key, CONV)
        self.assertEqual(report.morpheus_version, settings.MORPHEUS_VERSION)
        self.assertEqual(report.area, 'orders/export.py')

    def test_the_same_open_report_is_refreshed_not_duplicated(self):
        self._call({'title': 'Export 500s', 'problem': 'first'})
        self._call({'title': 'export 500s', 'problem': 'second, with more detail'})
        self.assertEqual(CodeProposal.objects.count(), 1)
        self.assertEqual(CodeProposal.objects.get().problem, 'second, with more detail')

    def test_an_external_agent_cannot_file(self):
        from core.agents import ToolError
        from core.assistant.tools.reports import reports_file_tool

        with self.assertRaises(ToolError):
            reports_file_tool.handler(
                title='t',
                problem='p',
                context={'user': self.user, 'conversation_key': 'ext:tok1:chat:abc'},
            )
        self.assertFalse(CodeProposal.objects.exists())

    def test_read_only_chat_modes_do_not_offer_it(self):
        import types

        from plugins.installed.agent_mcp.linda_turn import LindaTurn, catalogue

        user = types.SimpleNamespace(is_staff=True, is_superuser=False, pk=1)
        for mode, offered in (('general', True), ('dev', True), ('sales', False)):
            names = {
                t.name
                for t in catalogue(LindaTurn(user=user, conversation_key=CONV, mode_slug=mode))
            }
            self.assertEqual('reports.file' in names, offered, mode)


class IssueTests(TestCase):
    def test_the_issue_goes_to_the_configured_form_with_the_reviewed_text(self):
        report = _report(
            fix='Guard the division.', area='orders/export.py', morpheus_version='v9.9.9'
        )
        url = reports.issue_url(report)
        self.assertTrue(url.startswith(settings.MORPHEUS_REPORTS_URL + '?'))
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query['title'], ['Export 500s on empty stores'])
        body = query['body'][0]
        for part in ('divides by zero', 'Guard the division.', 'orders/export.py', 'v9.9.9'):
            self.assertIn(part, body)

    def test_contact_details_never_reach_the_public_issue(self):
        report = _report(problem='Fails for jane.doe@example.com from 203.0.113.9 every time.')
        body = reports.issue_body(report)
        self.assertNotIn('jane.doe@example.com', body)
        self.assertNotIn('203.0.113.9', body)

    def test_a_long_report_is_shortened_to_fit_a_url(self):
        report = _report(problem='x ' * 3000, fix='y ' * 3000)
        self.assertLessEqual(len(reports.issue_body(report)), reports.MAX_BODY)


class ReviewPageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_superuser('boss', 'boss@example.com', 'x')
        self.staff = User.objects.create_user('clerk', 'clerk@example.com', 'x', is_staff=True)
        self.report = _report()

    def _client(self, user):
        c = Client()
        c.force_login(user)
        return c

    def test_staff_can_read_but_not_send(self):
        c = self._client(self.staff)
        page = c.get(REPORTS)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Export 500s on empty stores')
        self.assertNotContains(page, 'Send to Morpheus')
        resp = c.post(f'{REPORTS}{self.report.id}/', {'action': 'send'})
        self.assertEqual(resp.status_code, 403)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, 'new')

    def test_sending_opens_github_with_the_edited_text_and_marks_it_sent(self):
        resp = self._client(self.owner).post(
            f'{REPORTS}{self.report.id}/',
            {
                'action': 'send',
                'title': 'CSV export fails with no orders',
                'problem': 'Edited by the owner.',
                'fix': '',
                'area': '',
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp['Location'].startswith(settings.MORPHEUS_REPORTS_URL))
        self.assertIn('Edited+by+the+owner', resp['Location'])
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, 'sent')
        self.assertEqual(self.report.title, 'CSV export fails with no orders')
        self.assertEqual(self.report.sent_by, 'boss@example.com')

    def test_a_report_without_a_problem_is_not_sent(self):
        resp = self._client(self.owner).post(
            f'{REPORTS}{self.report.id}/', {'action': 'send', 'title': 'x', 'problem': ' '}
        )
        self.assertEqual(resp['Location'], REPORTS)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, 'new')

    def test_dismiss_and_reopen(self):
        c = self._client(self.owner)
        c.post(f'{REPORTS}{self.report.id}/', {'action': 'dismiss'})
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, 'dismissed')
        c.post(f'{REPORTS}{self.report.id}/', {'action': 'reopen'})
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, 'new')

    def test_the_page_renders_with_no_reports(self):
        CodeProposal.objects.all().delete()
        page = self._client(self.owner).get(REPORTS)
        self.assertContains(page, 'No reports yet')
