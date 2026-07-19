"""Regression: the fallback cascade must honour a wall-clock budget.

`FallbackProviderRouter.respond` always tries the primary, but must SKIP a
secondary when starting its call could exceed the cascade budget
(`time.monotonic() + LLM_HTTP_TIMEOUT_SECS > deadline`, where
`deadline = start + LLM_FALLBACK_BUDGET_SECS`). Without this guard, a
connect-but-hang across N providers each burning a full 20s HTTP timeout could
stack past the 60s gunicorn worker budget and get the worker SIGKILLed (audit
H3). Here we shrink `LLM_FALLBACK_BUDGET_SECS` to trip the guard
deterministically — no real sleeps.
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import SimpleTestCase

import core.agents.llm as llm
from core.agents.llm import (
    DEGRADED_SENTINEL_CIRCUIT,
    FallbackProviderRouter,
    LLMProvider,
    LLMResponse,
    is_degraded_response,
)


class _RecordingProvider(LLMProvider):
    """A provider that records how many times it was called and returns a
    fixed, pre-scripted response."""

    def __init__(self, name: str, response: LLMResponse):
        self.name = name
        self.model = 'm'
        self._response = response
        self.calls = 0

    def respond(self, **_kw) -> LLMResponse:
        self.calls += 1
        return self._response


class FallbackBudgetTests(SimpleTestCase):
    def test_primary_always_runs_and_returns_when_healthy(self):
        # A healthy (non-degraded) primary returns immediately; the budget
        # guard never interferes and the secondary is never consulted.
        primary = _RecordingProvider('primary', LLMResponse(text='real answer', model='m'))
        secondary = _RecordingProvider('secondary', LLMResponse(text='rescued', model='m'))
        router = FallbackProviderRouter(primary, [secondary])

        resp = router.respond(messages=[], tools=[])

        self.assertEqual(resp.text, 'real answer')
        self.assertEqual(primary.calls, 1)
        self.assertEqual(secondary.calls, 0)

    def test_secondary_skipped_when_budget_exhausted(self):
        # Primary returns a DEGRADED sentinel, which would normally advance the
        # router to the secondary. With the cascade budget shrunk to 0, the
        # guard (`monotonic() + LLM_HTTP_TIMEOUT_SECS > deadline`) trips and the
        # secondary is NEVER started; the router returns the all-degraded sentinel.
        primary = _RecordingProvider(
            'primary',
            LLMResponse(text=f'{DEGRADED_SENTINEL_CIRCUIT} — circuit open]', model='m'),
        )
        secondary = _RecordingProvider('secondary', LLMResponse(text='rescued', model='m'))
        router = FallbackProviderRouter(primary, [secondary])

        with patch.object(llm, 'LLM_FALLBACK_BUDGET_SECS', 0):
            resp = router.respond(messages=[], tools=[])

        # Primary always runs; secondary is skipped by the budget guard.
        self.assertEqual(primary.calls, 1)
        self.assertEqual(secondary.calls, 0)
        # The router surfaces a degraded sentinel, not the secondary's rescue.
        self.assertTrue(is_degraded_response(resp.text))
        self.assertNotEqual(resp.text, 'rescued')

    def test_secondary_raising_on_call_would_prove_it_was_never_started(self):
        # Belt-and-braces: a secondary that raises if called at all. With the
        # budget exhausted it must never be invoked, so no exception surfaces.
        class _ExplodingSecondary(LLMProvider):
            name = 'secondary'
            model = 'm'

            def respond(self, **_kw):
                raise AssertionError('secondary must not be called past the budget')

        primary = _RecordingProvider(
            'primary',
            LLMResponse(text=f'{DEGRADED_SENTINEL_CIRCUIT} — circuit open]', model='m'),
        )
        router = FallbackProviderRouter(primary, [_ExplodingSecondary()])

        with patch.object(llm, 'LLM_FALLBACK_BUDGET_SECS', 0):
            resp = router.respond(messages=[], tools=[])

        self.assertEqual(primary.calls, 1)
        self.assertTrue(is_degraded_response(resp.text))
