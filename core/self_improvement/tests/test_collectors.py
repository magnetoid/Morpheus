"""Collector tests.

error_log regression (July 2026 audit): the collector read the RETIRED
`observability.ErrorEvent`, which nothing writes anymore (ADR 0025 moved the
write path to `core.errors.ErrorEvent`), so it silently ingested an empty
table. It now reads `core.errors.ErrorEvent` with the matching field names.
"""

from __future__ import annotations

from django.test import TestCase

from core.errors.models import ErrorEvent
from core.self_improvement.collectors.error_log import ErrorLogCollector
from core.self_improvement.services import fingerprint_for


class ErrorLogCollectorTests(TestCase):
    def test_reads_core_errors_and_maps_fields(self) -> None:
        ev = ErrorEvent.objects.create(
            kind='server',
            level='error',
            fingerprint='abc123',
            exception_class='KeyError',
            message="KeyError: 'seo_meta'",
            traceback='Traceback...\n  File "/app/plugins/x.py", line 9, in view\n    ...',
            path='/checkout/pay/',
        )

        signals = list(ErrorLogCollector().run())
        self.assertEqual(len(signals), 1)
        sig = signals[0]
        self.assertEqual(sig.source, 'error_log')
        # Fingerprint namespaces the model's own stable hash under SOURCE.
        self.assertEqual(sig.fingerprint, fingerprint_for('error_log', 'abc123'))
        self.assertEqual(sig.payload['exception_class'], 'KeyError')
        self.assertEqual(sig.payload['kind'], 'server')
        self.assertEqual(sig.payload['path'], '/checkout/pay/')
        self.assertEqual(sig.occurred_at, ev.created_at)
        # A checkout/payment path is a critical path → bumped severity.
        self.assertEqual(sig.severity, 85)

    def test_client_js_error_is_advisory_severity(self) -> None:
        ErrorEvent.objects.create(
            kind='client',
            level='error',
            fingerprint='js1',
            exception_class='TypeError',
            message='TypeError: undefined',
            path='/products/',
        )
        signals = list(ErrorLogCollector().run())
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].severity, 30)

    def test_no_events_yields_nothing(self) -> None:
        self.assertEqual(list(ErrorLogCollector().run()), [])
