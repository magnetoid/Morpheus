"""The circuit breaker re-opens when a probe fails (v0.197.0).

It tripped once per outage: after the cooldown it read half-open, a failed probe
changed nothing, and from then on every call waited out the dead dependency
again. The model provider's breaker is the one user, so a provider outage cost
its full timeout on every call after the first 30 seconds.
"""

from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase

from core.circuit_breaker import CircuitBreaker, CircuitOpenError


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class CircuitBreakerTests(SimpleTestCase):
    def setUp(self):
        self.clock = _Clock()
        patcher = mock.patch('core.circuit_breaker.time.time', self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.breaker = CircuitBreaker(name='test_breaker', failure_threshold=2, cooldown_seconds=30)
        self.addCleanup(CircuitBreaker._registry.pop, 'test_breaker', None)
        self.calls = 0

    def _call(self, fail=True):
        @self.breaker
        def dependency():
            self.calls += 1
            if fail:
                raise RuntimeError('down')
            return 'ok'

        return dependency()

    def _fail(self):
        with self.assertRaises(RuntimeError):
            self._call()

    def test_it_opens_at_the_threshold_and_fails_fast(self):
        with self.assertLogs('morpheus.circuit_breaker', level='WARNING'):
            self._fail()
            self._fail()
        self.assertEqual(self.breaker.state_label(), 'open')
        with self.assertRaises(CircuitOpenError):
            self._call()
        self.assertEqual(self.calls, 2)

    def test_a_failed_probe_opens_it_again(self):
        with self.assertLogs('morpheus.circuit_breaker', level='WARNING'):
            self._fail()
            self._fail()
        self.clock.now += 31
        self.assertEqual(self.breaker.state_label(), 'half_open')

        self._fail()  # the probe reaches the dependency and fails

        self.assertEqual(self.breaker.state_label(), 'open')
        with self.assertRaises(CircuitOpenError):
            self._call()
        self.assertEqual(self.calls, 3)

    def test_a_successful_probe_closes_it(self):
        with self.assertLogs('morpheus.circuit_breaker', level='WARNING'):
            self._fail()
            self._fail()
        self.clock.now += 31

        with self.assertLogs('morpheus.circuit_breaker', level='INFO'):
            self.assertEqual(self._call(fail=False), 'ok')

        self.assertEqual(self.breaker.state_label(), 'closed')
        self._fail()  # one failure after recovery does not trip it
        self.assertEqual(self.breaker.state_label(), 'closed')

    def test_only_breakers_in_use_are_listed(self):
        # Three module-level breakers nothing ran through were listed as
        # "closed", as if webhooks and the CDN were being measured.
        names = {row['name'] for row in CircuitBreaker.snapshot()}
        self.assertFalse(names & {'llm', 'webhook_outbound', 'cdn_api'})
