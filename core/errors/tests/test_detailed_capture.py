"""Detailed error capture: a switch with an end, more sources, a report for Claude Code.

Owner's ask (2026-10-11): a button on the error log that turns on a very
detailed capture, so Claude Code can later be pointed at each store to resolve
what it found. docs/plans/detailed-error-capture-2026-10.md has the design.

The switch memo and the request throttle are process-wide, so every test here
starts from and leaves them clean (CLAUDE.md: restore process-global state).
"""

from __future__ import annotations

import io
import logging
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import Client, RequestFactory, TestCase
from django.utils import timezone

from core.errors import mode
from core.errors import services as capture
from core.errors.models import ErrorCaptureMode, ErrorEvent, ErrorGroup


class _Clean(TestCase):
    def setUp(self):
        mode.forget()
        capture._throttle_seen.clear()
        self.addCleanup(mode.forget)
        self.addCleanup(capture._throttle_seen.clear)

    def _staff_client(self) -> Client:
        user = get_user_model().objects.create_user(
            username='err-staff', email='err@x.test', password='x', is_staff=True,
            is_superuser=True,
        )  # fmt: skip
        client = Client()
        client.force_login(user)
        return client


class SwitchTests(_Clean):
    def test_off_until_turned_on_and_off_again(self):
        self.assertFalse(mode.detailed_active())
        until = mode.turn_on(24)
        self.assertTrue(mode.detailed_active())
        self.assertAlmostEqual((until - timezone.now()).total_seconds(), 24 * 3600, delta=60)
        mode.turn_off()
        self.assertFalse(mode.detailed_active())

    def test_it_switches_itself_off_at_the_end_time(self):
        ErrorCaptureMode.objects.create(pk=1, detailed_until=timezone.now() - timedelta(minutes=1))
        mode.forget()
        self.assertFalse(mode.detailed_active())

    def test_a_window_is_capped(self):
        until = mode.turn_on(10_000)
        self.assertLessEqual(until - timezone.now(), timedelta(hours=mode.MAX_HOURS, minutes=1))

    def test_turning_it_on_is_audited(self):
        from core.audit.models import AuditEvent

        mode.turn_on(24)
        self.assertTrue(AuditEvent.objects.filter(event_type='errors.detailed_capture_on').exists())


class LogBridgeTests(_Clean):
    def _emit(self, level: int, msg: str, name: str = 'morpheus.catalog') -> None:
        from core.brain.log_handler import ErrorEventLogHandler

        record = logging.LogRecord(name, level, __file__, 10, msg, None, None)
        ErrorEventLogHandler(level=logging.WARNING).emit(record)

    def test_a_warning_is_kept_only_while_detailed_capture_is_on(self):
        self._emit(logging.WARNING, 'stock feed slow')
        self.assertFalse(ErrorEvent.objects.exists())
        mode.turn_on(24)
        self._emit(logging.WARNING, 'stock feed slower')
        event = ErrorEvent.objects.get()
        self.assertEqual(event.level, 'warning')
        self.assertIn('context', event.metadata)  # detailed events carry their context

    def test_an_error_is_always_kept(self):
        self._emit(logging.ERROR, 'payment provider down')
        self.assertEqual(ErrorEvent.objects.get().level, 'error')

    def test_request_warnings_are_left_to_the_middleware(self):
        mode.turn_on(24)
        self._emit(logging.WARNING, 'Not Found: /nope/', name='django.request')
        self.assertFalse(ErrorEvent.objects.exists())


class RequestCaptureTests(_Clean):
    def test_nothing_extra_is_recorded_while_off(self):
        client = self._staff_client()
        client.get('/dashboard/errors/detailed/')  # 405: POST only
        client.get('/no-such-page/', HTTP_REFERER='http://testserver/')
        self.assertFalse(ErrorEvent.objects.exists())

    def test_a_rejected_request_is_recorded_with_its_view(self):
        client = self._staff_client()
        mode.turn_on(24)
        self.assertEqual(client.get('/dashboard/errors/detailed/').status_code, 405)
        event = ErrorEvent.objects.get()
        self.assertEqual(event.status_code, 405)
        self.assertEqual(event.metadata['source'], 'rejected')
        self.assertEqual(event.metadata['context']['view'], 'errors:detailed')

    def test_a_broken_internal_link_is_recorded_once(self):
        mode.turn_on(24)
        client = Client()
        for _ in range(3):
            client.get('/gone-page/', HTTP_REFERER='http://testserver/journal/')
        event = ErrorEvent.objects.get()
        self.assertEqual(event.metadata['source'], 'broken_link')
        self.assertIn('/gone-page/', event.message)
        self.assertIn('/journal/', event.message)

    def test_a_404_from_elsewhere_is_not_a_broken_link(self):
        mode.turn_on(24)
        Client().get('/gone-page/', HTTP_REFERER='https://elsewhere.example/')
        Client().get('/gone-page/')
        self.assertFalse(ErrorEvent.objects.exists())

    def test_a_slow_response_is_recorded(self):
        mode.turn_on(24)
        with mock.patch('core.errors.middleware.SLOW_MS', -1):
            Client().get('/healthz/')  # skipped: a machine endpoint
            self.assertFalse(ErrorEvent.objects.exists())
            self._staff_client().get('/dashboard/errors/')
        event = ErrorEvent.objects.get(metadata__source='slow')
        self.assertEqual(event.exception_class, 'SlowResponse')

    def test_secret_query_values_are_not_kept(self):
        from core.errors.context import request_context

        request = RequestFactory().get('/products/', {'page': '2', 'token': 'abc123'})
        query = request_context(request)['query']
        self.assertEqual(query, {'page': '2', 'token': '[redacted]'})


class BrowserCaptureTests(_Clean):
    def _ingest(self, **payload):
        return Client().post(
            '/api/errors/client/',
            data={'message': 'Failed to load img: /media/x.jpg', **payload},
            content_type='application/json',
        )

    def test_detailed_browser_reports_are_dropped_while_off(self):
        self._ingest(name='ResourceError', level='warning', detail=True)
        self.assertFalse(ErrorEvent.objects.exists())

    def test_detailed_browser_reports_are_kept_while_on(self):
        mode.turn_on(24)
        self._ingest(name='ResourceError', level='warning', detail=True)
        event = ErrorEvent.objects.get()
        self.assertEqual((event.kind, event.level), ('client', 'warning'))
        self.assertTrue(event.metadata['detail'])

    def test_the_capture_script_learns_the_mode_from_its_tag(self):
        from django.template import Context, Template

        tpl = Template('{% load morph %}<script {% error_capture_attrs %}></script>')
        self.assertEqual(tpl.render(Context()), '<script ></script>')
        mode.turn_on(24)
        self.assertIn('data-detailed="1"', tpl.render(Context()))


def _crash(message: str = 'boom') -> None:
    try:
        raise KeyError(message)
    except KeyError as exc:
        capture.record_error(exc, kind='server')


class ReportTests(_Clean):
    def test_the_report_carries_what_a_fixer_needs(self):
        from core.errors.report import build_report, render_markdown

        _crash()
        report = build_report()
        self.assertEqual(len(report['groups']), 1)
        text = render_markdown(report)
        group = report['groups'][0]
        self.assertIn(group['fingerprint'], text)
        self.assertIn('How to work through this', text)
        self.assertIn("KeyError: 'boom'", text)
        self.assertIn('Traceback (latest occurrence)', text)

    def test_errors_come_before_warnings(self):
        from core.errors.report import build_report

        for i in range(3):
            capture.record_message(f'noisy warning {i}', level='warning', source='x')
        _crash()
        groups = build_report()['groups']
        self.assertEqual(groups[0]['level'], 'error')

    def test_a_resolved_group_leaves_the_report_until_it_fires_again(self):
        from core.errors.report import build_report, resolve

        _crash()
        fingerprint = ErrorEvent.objects.get().fingerprint
        self.assertTrue(resolve(fingerprint))
        self.assertEqual(build_report()['groups'], [])
        ErrorGroup.objects.filter(pk=fingerprint).update(
            resolved_at=timezone.now() - timedelta(minutes=5)
        )
        _crash()
        groups = build_report()['groups']
        self.assertEqual([g['status'] for g in groups], ['regressed'])

    def test_the_command_prints_the_report_and_resolves(self):
        _crash()
        fingerprint = ErrorEvent.objects.get().fingerprint
        out = io.StringIO()
        call_command('errors_report', stdout=out)
        self.assertIn(fingerprint, out.getvalue())
        call_command('errors_report', resolve=fingerprint, stdout=io.StringIO())
        self.assertEqual(ErrorGroup.objects.get(pk=fingerprint).status, 'resolved')
        with self.assertRaises(CommandError):
            call_command('errors_report', resolve='nope', stdout=io.StringIO())


class PageTests(_Clean):
    def test_the_switch_needs_staff_and_a_post(self):
        self.assertEqual(
            Client().post('/dashboard/errors/detailed/', {'hours': 24}).status_code, 302
        )
        self.assertFalse(mode.detailed_active())
        client = self._staff_client()
        client.post('/dashboard/errors/detailed/', {'hours': 168})
        mode.forget()
        until = mode.detailed_until()
        self.assertAlmostEqual((until - timezone.now()).total_seconds(), 168 * 3600, delta=120)
        page = client.get('/dashboard/errors/').content.decode()
        self.assertIn('Detailed capture', page)
        self.assertIn('Turn off', page)
        client.post('/dashboard/errors/detailed/', {'action': 'off'})
        mode.forget()
        self.assertFalse(mode.detailed_active())

    def test_the_report_downloads_as_markdown_and_json(self):
        _crash()
        client = self._staff_client()
        md = client.get('/dashboard/errors/report/?download=1')
        self.assertEqual(md['Content-Type'], 'text/markdown; charset=utf-8')
        self.assertIn('attachment;', md['Content-Disposition'])
        data = client.get('/dashboard/errors/report/?format=json').json()
        self.assertEqual(len(data['groups']), 1)
        self.assertEqual(Client().get('/dashboard/errors/report/').status_code, 302)

    def test_resolving_from_the_detail_page(self):
        _crash()
        fingerprint = ErrorEvent.objects.get().fingerprint
        client = self._staff_client()
        client.post(f'/dashboard/errors/{fingerprint}/resolve/', {'action': 'resolve'})
        self.assertEqual(ErrorGroup.objects.get(pk=fingerprint).status, 'resolved')
        page = client.get(f'/dashboard/errors/{fingerprint}/').content.decode()
        self.assertIn('Open again', page)
        listing = client.get('/dashboard/errors/').content.decode()
        self.assertNotIn(fingerprint, listing)  # open groups by default


class AgentToolTests(_Clean):
    def test_the_report_is_an_agent_tool_behind_diagnostics_read(self):
        from core.agents import ToolError, agent_registry

        _crash()
        recent = agent_registry.get_tool('errors.recent')
        self.assertEqual(list(recent.scopes), ['diagnostics.read'])
        output = recent.invoke({}).output
        self.assertEqual(len(output['groups']), 1)
        fingerprint = output['groups'][0]['fingerprint']
        got = agent_registry.get_tool('errors.get').invoke({'fingerprint': fingerprint}).output
        self.assertIn('Traceback', got['latest']['traceback'])
        with self.assertRaises(ToolError):
            agent_registry.get_tool('errors.get').invoke({'fingerprint': 'nope'})


class FingerprintTests(_Clean):
    def test_volatile_ids_do_not_split_one_problem_into_many_groups(self):
        # A provider puts a fresh request id in every error; one problem per day
        # became one group per day (dotbooks and Supernatural, 2026-10-09/10).
        for rid in ('e56bf010-1d2c-4f3b-9a8e-0f32b9096c11', '20e8c068-f144-40ae-928e-a7adcd9d606c'):
            capture.record_message(
                f'OpenAI completion error: Error code: 402 - Insufficient Balance (request_id: {rid})',
                source='log:morpheus.ai.llm',
            )
        capture.record_message(
            'Nightly backup failed: /app/backups/morpheus-backup-20260927T033000Z.tar.gz',
            source='backups',
        )
        capture.record_message(
            'Nightly backup failed: /app/backups/morpheus-backup-20260928T033000Z.tar.gz',
            source='backups',
        )
        self.assertEqual(ErrorEvent.objects.values('fingerprint').distinct().count(), 2)

    def test_an_id_partly_scrubbed_as_a_phone_number_is_still_the_same_problem(self):
        # The PII scrubber reads a run of digits inside a request id as a phone
        # number and hashes it, so the id no longer looked like a uuid and the
        # daily 402 still split into one group per day (dotbooks, 2026-10-11).
        for rid in ('ccad8165-edb5-484d-b3f8-996778530193', '20e8c068-f144-40ae-928e-a7adcd9d606c'):
            capture.record_message(
                f'OpenAI completion error: Error code: 402 - Insufficient Balance (request_id: {rid})',
                source='log:morpheus.ai.llm',
            )
        self.assertEqual(ErrorEvent.objects.values('fingerprint').distinct().count(), 1)

    def test_different_status_codes_stay_different_problems(self):
        capture.record_message('Upstream answered 402', source='x')
        capture.record_message('Upstream answered 500', source='x')
        self.assertEqual(ErrorEvent.objects.values('fingerprint').distinct().count(), 2)
