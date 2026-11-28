"""Every Linda turn is a run the store can see.

A Janus turn wrote only an ``AssistantMessage``; everything that reports — the
Observability page, the failure list, the AI-Act run summary — reads
``AgentRun``, so a Janus-only store showed an empty page against thousands of
turns (Irving: 0 runs, 42 replies, 6 M prompt tokens in a week). A turn now
also records an ``AgentRun`` with ``agent_name='linda'``: provider, model,
tokens, tool calls, the error. Her tokens keep counting toward the spend cap
exactly once — the cap reads them from her replies, so the Worker aggregates
skip her rows.
"""

from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.agents.models import AgentRun
from core.assistant.runtime import Assistant


class LindaRunTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='linda-run', email='lr@x.test', password='pw', is_staff=True
        )

    def _turn(self, payload, key='user:1:chat:abc'):
        with (
            mock.patch('core.assistant.janus_engine.janus_available', return_value=True),
            mock.patch(
                'core.assistant.janus_engine.iter_janus_turn',
                side_effect=lambda **kw: iter([payload]),
            ),
        ):
            return list(
                Assistant().stream(
                    message='how is stock?', conversation_key=key, context={'user': self.user}
                )
            )

    def test_a_completed_turn_is_a_run(self):
        self._turn(
            {
                'text': 'Fine.',
                'error': '',
                'duration_ms': 5,
                'provider': 'deepseek',
                'usage': {'model': 'deepseek-chat', 'input_tokens': 10, 'output_tokens': 5},
            }
        )
        run = AgentRun.objects.get()
        self.assertEqual(run.agent_name, 'linda')
        self.assertEqual(run.state, 'completed')
        self.assertEqual((run.provider, run.model), ('deepseek', 'deepseek-chat'))
        self.assertEqual((run.prompt_tokens, run.completion_tokens), (10, 5))
        self.assertEqual((run.user_message, run.final_text), ('how is stock?', 'Fine.'))
        self.assertEqual(run.metadata.get('conversation'), 'user:1:chat:abc')
        self.assertEqual(run.customer_id, self.user.pk)
        self.assertIsNotNone(run.ended_at)

    def test_a_run_names_the_janus_build_and_what_janus_counted(self):
        self._turn(
            {
                'text': 'Fine.',
                'error': '',
                'duration_ms': 5,
                'build': {'version': '0.18.0', 'commit': 'e' * 40},
                'usage': {
                    'model': 'deepseek-chat',
                    'input_tokens': 10,
                    'output_tokens': 5,
                    'reasoning_tokens': 7,
                    'api_call_count': 3,
                    'estimated_cost_usd': 0.0012345678,
                },
            }
        )
        meta = AgentRun.objects.get().metadata
        self.assertEqual((meta['janus_version'], meta['janus_commit']), ('0.18.0', 'e' * 40))
        self.assertEqual((meta['reasoning_tokens'], meta['api_calls']), (7, 3))
        self.assertEqual(meta['cost_usd'], 0.001235)

    def test_a_failed_run_names_the_build_the_turn_carried(self):
        # The run reads the build the turn ran (janus_engine.build_of on its own
        # command), never one looked up again after it.
        failed = {'version': '0.19.0', 'commit': 'f' * 40}
        with mock.patch('core.assistant.janus_binary._build_of', return_value=('0.18.0', 'e' * 40)):
            self._turn({'text': '', 'error': 'janus exited 1', 'duration_ms': 5, 'build': failed})
        meta = AgentRun.objects.get().metadata
        self.assertEqual((meta['janus_version'], meta['janus_commit']), ('0.19.0', 'f' * 40))

    def test_an_unknown_build_still_records_the_run(self):
        # Tests point JANUS_BIN at a path that does not exist: nothing to read.
        self._turn({'text': 'ok', 'error': '', 'duration_ms': 5, 'usage': {}})
        meta = AgentRun.objects.get().metadata
        self.assertEqual((meta['janus_version'], meta['janus_commit']), ('', ''))
        self.assertEqual((meta['api_calls'], meta['cost_usd']), (0, 0.0))

    def test_a_failed_turn_is_a_failed_run(self):
        self._turn({'text': '', 'error': 'janus timed out', 'duration_ms': 5, 'usage': {}})
        run = AgentRun.objects.get()
        self.assertEqual(run.state, 'failed')
        self.assertIn('timed out', run.error)

    def test_the_spend_cap_counts_her_once_and_the_run_cap_not_at_all(self):
        from core.agents.guardrails import daily_run_count, daily_spend_usd
        from core.agents.pricing import estimate_cost

        self._turn(
            {
                'text': 'ok',
                'error': '',
                'duration_ms': 5,
                'provider': 'deepseek',
                'usage': {'model': 'deepseek-chat', 'input_tokens': 1_000_000, 'output_tokens': 0},
            }
        )
        self.assertEqual(AgentRun.objects.filter(agent_name='linda').count(), 1)
        self.assertAlmostEqual(
            daily_spend_usd(), estimate_cost('deepseek-chat', 1_000_000, 0), places=6
        )
        self.assertEqual(daily_run_count(), 0)
