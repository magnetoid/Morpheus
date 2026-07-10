"""Brain hardening — error-log handler, analyst caching, signal cache, digest."""

import logging
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from core.brain.log_handler import ErrorEventLogHandler


def _record(name='morpheus.foo', msg='boom', module='m', lineno=1):
    rec = logging.LogRecord(name, logging.ERROR, '/p.py', lineno, msg, None, None)
    rec.module = module
    return rec


class ErrorLogHandlerTests(SimpleTestCase):
    # The handler writes through core.errors.services (ADR 0025) —
    # record_message for plain log records, record_error when exc_info holds
    # a live exception. Patch there, not the old observability path.
    @patch('core.errors.services.record_message')
    def test_records_error_event(self, rec):
        ErrorEventLogHandler().emit(_record())
        self.assertEqual(rec.call_count, 1)
        args, kw = rec.call_args
        self.assertTrue(kw['source'].startswith('log:'))
        self.assertEqual(args[0], 'boom')

    @patch('core.errors.services.record_message')
    def test_denylisted_logger_ignored(self, rec):
        # Its own subsystem's loggers must never re-enter (loop guard).
        for name in ('morpheus.observability.x', 'morpheus.brain', 'django.db.backends'):
            ErrorEventLogHandler().emit(_record(name=name))
        rec.assert_not_called()

    @patch('core.errors.services.record_message')
    def test_throttle_dedupes_same_fingerprint(self, rec):
        h = ErrorEventLogHandler()
        h.emit(_record())
        h.emit(_record())
        self.assertEqual(rec.call_count, 1)

    @patch('core.errors.services.record_message', side_effect=RuntimeError('db down'))
    def test_fail_soft_never_raises(self, rec):
        ErrorEventLogHandler().emit(_record())  # must not raise


class AnalystCacheTests(TestCase):
    def setUp(self):
        cache.clear()

    @patch('core.brain.analyst.analyze')
    def test_error_result_not_cached_success_is(self, analyze):
        from core.brain import analyst

        analyze.return_value = {'configured': True, 'error': 'boom', 'recommendations': []}
        analyst.get_analysis(force=True)
        self.assertIsNone(analyst.cached_analysis())  # failure not pinned

        analyze.return_value = {
            'configured': True,
            'summary': 'ok',
            'recommendations': [{'title': 'x'}],
        }
        analyst.get_analysis(force=True)
        self.assertIsNotNone(analyst.cached_analysis())  # success cached

    @patch('core.brain.analyst.analyze')
    def test_unconfigured_not_cached(self, analyze):
        from core.brain import analyst

        analyze.return_value = {'configured': False, 'message': 'no ai', 'recommendations': []}
        analyst.get_analysis(force=True)
        self.assertIsNone(analyst.cached_analysis())


class SignalsCacheTests(TestCase):
    def setUp(self):
        cache.clear()

    @patch('core.brain.signals._gather_all_uncached', return_value={'plugins': {}})
    def test_cached_then_invalidated(self, uncached):
        from core.brain import signals

        signals.gather_all()
        signals.gather_all()
        self.assertEqual(uncached.call_count, 1)  # 2nd served from cache
        signals.invalidate_signals_cache()
        signals.gather_all()
        self.assertEqual(uncached.call_count, 2)  # re-queried after invalidation


class DigestTests(SimpleTestCase):
    def test_summarize_includes_merchant_insights(self):
        from core.brain.analyst import _summarize_signals

        text = _summarize_signals(
            {
                'improvements': {
                    'insights': [{'title': 'Low stock alert', 'priority': 'high', 'type': 'risk'}],
                    'setup': [{'title': 'Add an AI key'}],
                }
            }
        )
        self.assertIn('Low stock alert', text)
        self.assertIn('Add an AI key', text)
