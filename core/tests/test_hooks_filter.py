"""HookRegistry.filter isolation vs fail-closed.

By default a raising filter handler is isolated (logged, skipped) so one buggy
subscriber can't break the pipeline. Security-critical filters (the MFA
second-factor gate) pass ``raise_errors=True`` so a handler exception
propagates and the caller can fail CLOSED instead of reading the swallowed
"no transformation" as "no second factor required".
"""

from __future__ import annotations

from django.test import TestCase

from core.hooks import HookRegistry

EVENT = 'test.filter.event'


class FilterIsolationTests(TestCase):
    def test_raising_handler_is_isolated_by_default(self):
        reg = HookRegistry()

        def boom(value, **kwargs):
            raise RuntimeError('handler blew up')

        reg.register(EVENT, boom)
        # Default: the exception is swallowed, the unchanged value is returned.
        self.assertIsNone(reg.filter(EVENT, value=None))

    def test_raise_errors_propagates_for_fail_closed_callers(self):
        reg = HookRegistry()

        def boom(value, **kwargs):
            raise RuntimeError('handler blew up')

        reg.register(EVENT, boom)
        with self.assertRaises(RuntimeError):
            reg.filter(EVENT, value=None, raise_errors=True)

    def test_healthy_handler_still_transforms_with_raise_errors(self):
        reg = HookRegistry()

        def gate(value, **kwargs):
            return 'challenge-response'

        reg.register(EVENT, gate)
        self.assertEqual(reg.filter(EVENT, value=None, raise_errors=True), 'challenge-response')
