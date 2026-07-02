"""Error capture is a single CORE system (ADR 0025).

Verifies the consolidation: `record_error` (exception path) and `record_message`
(string path) both write to `core/errors.ErrorEvent`, and the deprecated
observability-plugin `record_error` shim now forwards into core instead of its
own retired parallel table — so Celery / API / GraphQL / brain-log errors all
land in one fingerprinted table (was split across two).
"""

from __future__ import annotations

from django.test import TestCase

from core.errors.models import ErrorEvent
from core.errors.services import record_error, record_message


class CoreCaptureTests(TestCase):
    def test_record_error_writes_core_event_with_frame_fingerprint(self):
        try:
            raise ValueError('boom')
        except ValueError as e:
            record_error(e, kind='server', extra={'source': 'celery'})
        ev = ErrorEvent.objects.get()
        self.assertEqual(ev.exception_class, 'ValueError')
        self.assertEqual(ev.kind, 'server')
        self.assertEqual(ev.metadata.get('source'), 'celery')
        self.assertIn('boom', ev.message)
        self.assertTrue(ev.fingerprint)

    def test_record_message_writes_core_event(self):
        record_message(
            'something failed',
            kind='server',
            source='log:foo',
            level='warning',
            extra={'logger': 'foo'},
        )
        ev = ErrorEvent.objects.get()
        self.assertEqual(ev.kind, 'server')
        self.assertEqual(ev.level, 'warning')
        self.assertEqual(ev.metadata.get('source'), 'log:foo')
        self.assertTrue(ev.fingerprint)

    def test_message_fingerprint_dedups_same_source_and_message(self):
        record_message('repeated', source='x')
        record_message('repeated', source='x')
        fps = set(ErrorEvent.objects.values_list('fingerprint', flat=True))
        self.assertEqual(len(fps), 1)  # same (source, message) => one fingerprint


class ObservabilityShimTests(TestCase):
    def test_plugin_record_error_forwards_to_core(self):
        from plugins.installed.observability.models import ErrorEvent as PluginErrorEvent
        from plugins.installed.observability.services import record_error as plugin_record_error

        plugin_record_error(
            source='api.rest', message='legacy call', stack_trace='trace', metadata={'k': 'v'}
        )
        # Lands in the CORE table, NOT the retired plugin table.
        self.assertEqual(ErrorEvent.objects.count(), 1)
        self.assertEqual(PluginErrorEvent.objects.count(), 0)
        ev = ErrorEvent.objects.get()
        self.assertEqual(ev.metadata.get('source'), 'api.rest')
        self.assertEqual(ev.metadata.get('k'), 'v')


class LogToolTests(TestCase):
    """The assistant's log tools read the CORE error log (not the frozen
    observability plugin table)."""

    def test_recent_errors_tool_reads_core_log(self):
        from core.assistant.tools.logs import recent_errors_tool

        try:
            raise RuntimeError('kaboom')
        except RuntimeError as e:
            record_error(e, kind='server', extra={'source': 'celery'})
        errs = recent_errors_tool.handler(hours=6, limit=10).output['errors']
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0]['source'], 'celery')
        self.assertEqual(errs[0]['exception'], 'RuntimeError')
        self.assertIn('kaboom', errs[0]['message'])
