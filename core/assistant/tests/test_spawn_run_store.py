"""A spawned Worker's run is saved like every other run (v0.199.0).

The spawned Worker had its own copy of step saving and of the end-of-run
write. It never marked a run whose step could not be saved, and a run that
raised was closed with no tokens and no model, which the spend cap counts as
free.
"""

from __future__ import annotations

from unittest import mock

from django.db import DatabaseError
from django.test import TestCase

from core.agents import AgentRuntime
from core.agents.llm import LLMResponse, MockLLMProvider
from core.agents.models import AgentRun, AgentStep
from core.assistant.tools import spawn


class SpawnedWorkerRunTests(TestCase):
    def _worker_run(self, provider):
        provider.model = 'gpt-4o-mini'
        run = AgentRun.objects.create(
            agent_name='worker',
            audience='any',
            user_message='tidy up',
            state='running',
            metadata={'batch_id': 'b1'},
        )
        with mock.patch('core.agents.get_llm_provider', return_value=provider):
            spawn._execute_worker_run(run_id=str(run.id), objective='tidy up', context={})
        return AgentRun.objects.get(pk=run.pk)

    def test_a_finished_run_is_written_with_its_steps(self):
        provider = MockLLMProvider(
            [LLMResponse(text='done', prompt_tokens=100, completion_tokens=20)], echo_user=False
        )
        row = self._worker_run(provider)

        self.assertEqual((row.state, row.final_text), ('completed', 'done'))
        self.assertEqual((row.prompt_tokens, row.completion_tokens), (100, 20))
        self.assertEqual((row.provider, row.model), ('mock', 'gpt-4o-mini'))
        self.assertEqual(row.metadata, {'batch_id': 'b1'})
        kinds = list(
            AgentStep.objects.filter(run=row).order_by('seq').values_list('kind', flat=True)
        )
        self.assertEqual(kinds[-2:], ['user', 'final'])

    def test_a_run_that_raises_keeps_what_it_spent(self):
        def crashing(*, usage, **_kw):
            usage.add('gpt-4o-mini', 40, 4)
            raise RuntimeError('boom')

        with (
            mock.patch.object(AgentRuntime, 'run', side_effect=crashing),
            self.assertLogs('morpheus.assistant.spawn', level='ERROR'),
        ):
            row = self._worker_run(MockLLMProvider([]))

        self.assertEqual((row.state, row.error), ('failed', 'RuntimeError: boom'))
        self.assertEqual(
            (row.prompt_tokens, row.completion_tokens, row.model), (40, 4, 'gpt-4o-mini')
        )

    def test_a_step_that_cannot_be_saved_marks_the_run(self):
        provider = MockLLMProvider([LLMResponse(text='done')], echo_user=False)
        with (
            mock.patch.object(AgentStep.objects, 'create', side_effect=DatabaseError('down')),
            self.assertLogs('morpheus.agents.run_store', level='WARNING'),
        ):
            row = self._worker_run(provider)

        self.assertEqual(row.state, 'completed')
        self.assertTrue(row.metadata['audit_incomplete'])

    def test_a_missing_worker_agent_fails_the_run(self):
        run = AgentRun.objects.create(agent_name='worker', user_message='x', state='running')
        with mock.patch('core.agents.agent_registry.get_agent', return_value=None):
            spawn._execute_worker_run(run_id=str(run.id), objective='x', context={})
        row = AgentRun.objects.get(pk=run.pk)
        self.assertEqual((row.state, row.error), ('failed', 'worker agent not registered'))
