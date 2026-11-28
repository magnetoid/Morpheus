"""A run that does not end well still says what it spent (v0.199.0).

`run_agent` closed a timed-out or crashed run with no tokens and no model, so
the spend cap counted it as free, and the thread a timeout leaves behind went
on spending with nothing to record it. A run whose row could not be created
was not counted at all.
"""

from __future__ import annotations

import sys
import threading
from types import SimpleNamespace
from unittest import mock

from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase

import plugins.installed.agent_core.services as svc
from core.agents import LLMResponse, MockLLMProvider, MorpheusAgent
from core.agents.models import AgentRun, ModelUsageDay
from core.agents.usage import USAGE_KEY
from morpheus.core import agent_registry


def _spend_agent():
    # A bare instance, never a subclass (the pre-commit hook refuses those).
    agent = MorpheusAgent()
    agent.name = 'spend_agent'
    agent.label = 'Spend Agent'
    agent.audience = 'system'
    agent.scopes = []
    agent.max_steps = 3
    agent.get_tools = lambda: []
    return agent


class _Registered(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        agent_registry.register_agent(_spend_agent(), plugin='__test_run_spend')
        cls.addClassCleanup(agent_registry.drop_plugin, '__test_run_spend')

    def _provider(self, *replies):
        provider = MockLLMProvider(list(replies), echo_user=False)
        provider.model = 'gpt-4o-mini'
        patcher = mock.patch.object(svc, 'get_llm_provider', return_value=provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        return provider


class RunEndTests(_Registered):
    def test_a_finished_run_writes_its_tokens_and_model(self):
        self._provider(LLMResponse(text='done', prompt_tokens=100, completion_tokens=20))

        svc.run_agent(agent_name='spend_agent', user_message='go')

        row = AgentRun.objects.get()
        self.assertEqual((row.state, row.final_text), ('completed', 'done'))
        self.assertEqual((row.prompt_tokens, row.completion_tokens), (100, 20))
        self.assertEqual((row.provider, row.model), ('mock', 'gpt-4o-mini'))
        self.assertNotIn(USAGE_KEY, row.metadata)

    def test_an_answer_from_the_fallback_model_is_kept_apart(self):
        self._provider(
            LLMResponse(text='done', prompt_tokens=100, completion_tokens=20, model='claude-opus-4')
        )

        svc.run_agent(agent_name='spend_agent', user_message='go')

        row = AgentRun.objects.get()
        self.assertEqual(row.model, 'gpt-4o-mini')
        self.assertEqual(row.metadata[USAGE_KEY], {'claude-opus-4': [100, 20]})

    def test_a_timed_out_run_keeps_what_it_spent(self):
        provider = self._provider()

        def timing_out(*, usage, **_kw):
            usage.add('gpt-4o-mini', 70, 9)
            raise TimeoutError('agent runtime exceeded 45.0s')

        with (
            mock.patch.object(svc, '_run_with_timeout', side_effect=timing_out),
            self.assertRaises(TimeoutError),
            self.assertLogs('morpheus.agents.services', level='WARNING'),
        ):
            svc.run_agent(agent_name='spend_agent', user_message='go')

        row = AgentRun.objects.get()
        self.assertEqual((row.state, row.error), ('failed', 'timeout after 45.0s'))
        self.assertEqual((row.prompt_tokens, row.completion_tokens), (70, 9))
        self.assertEqual((row.provider, row.model), (provider.name, 'gpt-4o-mini'))

    def test_the_thread_a_timeout_leaves_behind_writes_its_last_tokens(self):
        self._provider()
        seen = {}

        def timing_out(*, usage, on_late, **_kw):
            usage.add('gpt-4o-mini', 70, 9)
            seen.update(usage=usage, on_late=on_late)
            raise TimeoutError('agent runtime exceeded 45.0s')

        with (
            mock.patch.object(svc, '_run_with_timeout', side_effect=timing_out),
            self.assertRaises(TimeoutError),
            self.assertLogs('morpheus.agents.services', level='WARNING'),
        ):
            svc.run_agent(agent_name='spend_agent', user_message='go')

        # The provider call that was in flight answers after the request gave up.
        seen['usage'].add('gpt-4o-mini', 30, 6)
        with mock.patch.object(svc, '_close_thread_connection'):
            seen['on_late']()

        row = AgentRun.objects.get()
        self.assertEqual((row.prompt_tokens, row.completion_tokens), (100, 15))
        self.assertEqual((row.state, row.error), ('failed', 'timeout after 45.0s'))

    def test_the_late_write_and_the_timeout_agree_in_either_order(self):
        # The thread may end in the instant the caller gives up, and write first.
        self._provider()

        def timing_out(*, usage, on_late, **_kw):
            usage.add('gpt-4o-mini', 100, 15)
            with mock.patch.object(svc, '_close_thread_connection'):
                on_late()
            raise TimeoutError('agent runtime exceeded 45.0s')

        with (
            mock.patch.object(svc, '_run_with_timeout', side_effect=timing_out),
            self.assertRaises(TimeoutError),
            self.assertLogs('morpheus.agents.services', level='WARNING'),
        ):
            svc.run_agent(agent_name='spend_agent', user_message='go')

        row = AgentRun.objects.get()
        self.assertEqual((row.prompt_tokens, row.completion_tokens), (100, 15))
        self.assertEqual((row.state, row.error), ('failed', 'timeout after 45.0s'))

    def test_a_late_run_with_no_row_is_counted_once(self):
        self._provider()
        seen = {}

        def timing_out(*, usage, on_late, **_kw):
            usage.add('gpt-4o-mini', 70, 9)
            seen.update(usage=usage, on_late=on_late)
            raise TimeoutError('agent runtime exceeded 45.0s')

        with (
            mock.patch.object(AgentRun.objects, 'create', side_effect=DatabaseError('down')),
            mock.patch.object(svc, '_run_with_timeout', side_effect=timing_out),
            self.assertRaises(TimeoutError),
            self.assertLogs('morpheus.agents.services', level='WARNING'),
        ):
            svc.run_agent(agent_name='spend_agent', user_message='go')

        seen['usage'].add('gpt-4o-mini', 30, 6)
        with mock.patch.object(svc, '_close_thread_connection') as closed:
            seen['on_late']()

        day = ModelUsageDay.objects.get()
        self.assertEqual((day.prompt_tokens, day.completion_tokens), (100, 15))
        closed.assert_called_once()

    def test_a_run_that_raises_keeps_what_it_spent(self):
        self._provider()

        def crashing(*, usage, **_kw):
            usage.add('gpt-4o-mini', 40, 4)
            raise RuntimeError('boom')

        with (
            mock.patch.object(svc, '_run_with_timeout', side_effect=crashing),
            self.assertRaises(RuntimeError),
            self.assertLogs('morpheus.agents.services', level='ERROR'),
        ):
            svc.run_agent(agent_name='spend_agent', user_message='go')

        row = AgentRun.objects.get()
        self.assertEqual((row.state, row.error), ('failed', 'RuntimeError: boom'))
        self.assertEqual(
            (row.prompt_tokens, row.completion_tokens, row.model), (40, 4, 'gpt-4o-mini')
        )

    def test_a_run_with_no_row_is_counted_by_the_day(self):
        self._provider(LLMResponse(text='done', prompt_tokens=100, completion_tokens=20))

        with (
            mock.patch.object(AgentRun.objects, 'create', side_effect=DatabaseError('down')),
            self.assertLogs('morpheus.agents.services', level='WARNING'),
        ):
            result = svc.run_agent(agent_name='spend_agent', user_message='go')

        self.assertEqual(result.text, 'done')
        day = ModelUsageDay.objects.get()
        self.assertEqual(
            (day.model, day.prompt_tokens, day.completion_tokens), ('gpt-4o-mini', 100, 20)
        )


class TimeoutThreadTests(SimpleTestCase):
    """The threaded path itself, with no database in the thread."""

    def _threaded(self, runtime, **kw):
        # Under tests the helper runs inline; give it a server's argv.
        with mock.patch.object(sys, 'argv', ['gunicorn']):
            return svc._run_with_timeout(
                runtime=runtime, user_message='go', history=[], context={}, run_id='r1', **kw
            )

    def test_a_run_that_answers_in_time_is_returned(self):
        runtime = SimpleNamespace(run=lambda **kw: 'result')
        late = mock.Mock()
        self.assertEqual(self._threaded(runtime, timeout=5, on_late=late), 'result')
        late.assert_not_called()

    def test_the_meter_reaches_the_runtime(self):
        got = {}
        runtime = SimpleNamespace(run=lambda **kw: got.update(kw) or 'result')
        meter = object()
        self._threaded(runtime, timeout=5, usage=meter)
        self.assertIs(got['usage'], meter)

    def test_a_late_run_is_reported_once_it_ends(self):
        release, ended = threading.Event(), threading.Event()

        def slow(**_kw):
            release.wait(10)
            return 'late result'

        def late():
            ended.set()

        with self.assertRaises(TimeoutError):
            self._threaded(SimpleNamespace(run=slow), timeout=0.05, on_late=late)
        self.assertFalse(ended.is_set())

        release.set()
        self.assertTrue(ended.wait(10))

    def test_an_error_in_time_is_raised_and_not_reported_late(self):
        def boom(**_kw):
            raise ValueError('bad')

        late = mock.Mock()
        with self.assertRaises(ValueError):
            self._threaded(SimpleNamespace(run=boom), timeout=5, on_late=late)
        late.assert_not_called()
