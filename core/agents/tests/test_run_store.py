"""One place saves a run (v0.199.0).

Step saving and the end-of-run write existed twice, in agent_core's services
and in the spawned Worker's runner, and had drifted: only one marked a run whose
step could not be saved, and neither kept what a run spent when it timed out or
raised. `core/agents/run_store.py` is the one copy both call.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.db import DatabaseError
from django.test import TestCase

from core.agents import guardrails, run_store
from core.agents.models import AgentRun, AgentStep, ModelUsageDay
from core.agents.trace import TraceStep
from core.agents.usage import USAGE_KEY, RunUsage
from core.audit.models import AuditEvent


def _run(**fields):
    return AgentRun.objects.create(agent_name='worker', state='running', **fields)


def _provider(model='gpt-4o-mini'):
    return SimpleNamespace(name='openai', model=model)


def _result(state='completed', text='done', error='', tool_calls=1):
    return SimpleNamespace(state=state, text=text, error=error, tool_calls=tool_calls)


def _usage(**by_model):
    usage = RunUsage()
    for model, (pt, ct) in by_model.items():
        usage.add(model.replace('_', '-'), pt, ct)
    return usage


class StepMirrorTests(TestCase):
    def test_a_step_is_saved_and_a_tool_result_is_audited(self):
        run = _run()
        seen = []
        mirror = run_store.StepMirror(run, on_step=seen.append)

        mirror(TraceStep(kind='tool_call', name='orders.search', arguments={'q': 'x'}))
        mirror(TraceStep(kind='tool_result', name='orders.search', output={'count': 2}))

        rows = list(AgentStep.objects.filter(run=run).order_by('seq'))
        self.assertEqual(
            [(r.seq, r.kind, r.name) for r in rows],
            [(1, 'tool_call', 'orders.search'), (2, 'tool_result', 'orders.search')],
        )
        self.assertEqual(rows[1].output, {'count': 2})
        audit = AuditEvent.objects.get(event_type='agents.decision')
        self.assertEqual(audit.metadata['tool'], 'orders.search')
        self.assertEqual(audit.metadata['agent'], 'worker')
        self.assertEqual(audit.metadata['run_id'], str(run.pk))
        self.assertEqual(len(seen), 2)
        self.assertFalse(mirror.incomplete)

    def test_a_value_json_cannot_hold_is_saved_as_text(self):
        from decimal import Decimal

        run = _run()
        run_store.StepMirror(run)(TraceStep(kind='tool_result', name='t', output=Decimal('1.50')))
        self.assertEqual(AgentStep.objects.get(run=run).output, {'value': '1.50'})

    def test_a_step_that_cannot_be_saved_marks_the_run(self):
        run = _run()
        mirror = run_store.StepMirror(run)
        with (
            mock.patch.object(AgentStep.objects, 'create', side_effect=DatabaseError('down')),
            self.assertLogs('morpheus.agents.run_store', level='WARNING'),
        ):
            mirror(TraceStep(kind='assistant', content='thinking'))

        self.assertTrue(mirror.incomplete)
        run_store.finish(
            run,
            _result(),
            _provider(),
            RunUsage(),
            duration_ms=5,
            audit_incomplete=mirror.incomplete,
        )
        self.assertTrue(AgentRun.objects.get(pk=run.pk).metadata['audit_incomplete'])

    def test_a_tool_result_is_audited_even_when_its_step_is_not_saved(self):
        # The audit trail is the record a regulator asks for; it must not depend
        # on the step table taking the row.
        run = _run()
        mirror = run_store.StepMirror(run)
        with (
            mock.patch.object(AgentStep.objects, 'create', side_effect=DatabaseError('down')),
            self.assertLogs('morpheus.agents.run_store', level='WARNING'),
        ):
            mirror(TraceStep(kind='tool_result', name='orders.search', output={'count': 2}))

        self.assertTrue(mirror.incomplete)
        audit = AuditEvent.objects.get(event_type='agents.decision')
        self.assertEqual(audit.metadata['tool'], 'orders.search')

    def test_the_callers_listener_cannot_break_the_run(self):
        def boom(_step):
            raise RuntimeError('listener')

        run = _run()
        run_store.StepMirror(run, on_step=boom)(TraceStep(kind='assistant', content='x'))
        self.assertEqual(AgentStep.objects.filter(run=run).count(), 1)


class FinishTests(TestCase):
    def test_the_end_of_a_run_is_written(self):
        run = _run(metadata={'batch_id': 'b1'})
        run_store.finish(
            run, _result(), _provider(), _usage(gpt_4o_mini=(100, 20)), duration_ms=1234
        )

        row = AgentRun.objects.get(pk=run.pk)
        self.assertEqual((row.state, row.final_text, row.tool_call_count), ('completed', 'done', 1))
        self.assertEqual((row.prompt_tokens, row.completion_tokens), (100, 20))
        self.assertEqual(
            (row.provider, row.model, row.duration_ms), ('openai', 'gpt-4o-mini', 1234)
        )
        self.assertIsNotNone(row.ended_at)
        # One model answered, and it is the run's own: no split to keep.
        self.assertEqual(row.metadata, {'batch_id': 'b1'})

    def test_another_models_share_is_kept_with_the_run(self):
        run = _run()
        usage = _usage(gpt_4o_mini=(100, 20), claude_opus_4=(1000, 200))
        run_store.finish(run, _result(), _provider(), usage, duration_ms=1)

        row = AgentRun.objects.get(pk=run.pk)
        self.assertEqual((row.prompt_tokens, row.completion_tokens), (1100, 220))
        self.assertEqual(row.model, 'gpt-4o-mini')
        self.assertEqual(
            row.metadata[USAGE_KEY], {'gpt-4o-mini': [100, 20], 'claude-opus-4': [1000, 200]}
        )

    def test_a_failed_run_keeps_what_it_spent(self):
        run = _run()
        run_store.fail(
            run, 'timeout after 45.0s', _provider(), _usage(gpt_4o_mini=(70, 9)), duration_ms=45000
        )

        row = AgentRun.objects.get(pk=run.pk)
        self.assertEqual((row.state, row.error), ('failed', 'timeout after 45.0s'))
        self.assertEqual(
            (row.prompt_tokens, row.completion_tokens, row.model), (70, 9, 'gpt-4o-mini')
        )
        self.assertEqual(row.duration_ms, 45000)

    def test_a_run_that_failed_before_it_had_a_provider(self):
        run = _run()
        run_store.fail(run, 'worker agent not registered')
        row = AgentRun.objects.get(pk=run.pk)
        self.assertEqual(
            (row.state, row.error, row.prompt_tokens), ('failed', 'worker agent not registered', 0)
        )

    def test_tokens_that_arrive_after_the_row_was_closed(self):
        # The timed-out run's thread finishes its last provider call later.
        run = _run()
        usage = _usage(gpt_4o_mini=(70, 9))
        run_store.fail(run, 'timeout after 45.0s', _provider(), usage, duration_ms=45000)
        usage.add('gpt-4o-mini', 30, 6)

        run_store.save_usage(run, _provider(), usage)

        row = AgentRun.objects.get(pk=run.pk)
        self.assertEqual((row.prompt_tokens, row.completion_tokens), (100, 15))
        self.assertEqual((row.state, row.error), ('failed', 'timeout after 45.0s'))


class SpendCapTests(TestCase):
    def test_a_split_run_is_priced_by_the_models_that_answered(self):
        # 1M prompt tokens: $0.15 on gpt-4o-mini, $15 on claude-opus-4.
        run = _run()
        usage = _usage(claude_opus_4=(1_000_000, 0))
        run_store.finish(run, _result(), _provider('gpt-4o-mini'), usage, duration_ms=1)

        self.assertAlmostEqual(guardrails.daily_spend_usd(), 15.0, places=2)

    def test_runs_without_a_split_are_priced_as_before(self):
        run_store.finish(
            _run(), _result(), _provider(), _usage(gpt_4o_mini=(1_000_000, 0)), duration_ms=1
        )
        run_store.finish(
            _run(), _result(), _provider(), _usage(gpt_4o_mini=(1_000_000, 0)), duration_ms=1
        )
        self.assertAlmostEqual(guardrails.daily_spend_usd(), 0.30, places=2)

    def test_the_current_run_is_left_out_of_both_kinds(self):
        plain, split = _run(), _run()
        run_store.finish(
            plain, _result(), _provider(), _usage(gpt_4o_mini=(1_000_000, 0)), duration_ms=1
        )
        run_store.finish(
            split, _result(), _provider(), _usage(claude_opus_4=(1_000_000, 0)), duration_ms=1
        )

        self.assertAlmostEqual(guardrails.daily_spend_usd(exclude_id=split.pk), 0.15, places=2)
        self.assertAlmostEqual(guardrails.daily_spend_usd(exclude_id=plain.pk), 15.0, places=2)

    def test_a_second_count_of_a_run_with_no_row_adds_only_what_is_new(self):
        usage = _usage(gpt_4o_mini=(100, 10))
        counted = run_store.record_unstored(_provider(), usage)
        usage.add('gpt-4o-mini', 30, 5)

        run_store.record_unstored(_provider(), usage, counted=counted)

        day = ModelUsageDay.objects.get()
        self.assertEqual((day.prompt_tokens, day.completion_tokens), (130, 15))

    def test_a_run_with_no_row_is_counted_by_the_day(self):
        run_store.record_unstored(
            _provider(), _usage(gpt_4o_mini=(1_000_000, 0), claude_opus_4=(10, 5))
        )

        rows = {
            r.model: (r.prompt_tokens, r.completion_tokens) for r in ModelUsageDay.objects.all()
        }
        self.assertEqual(rows, {'gpt-4o-mini': (1_000_000, 0), 'claude-opus-4': (10, 5)})
        self.assertGreater(guardrails.daily_spend_usd(), 0.15)
