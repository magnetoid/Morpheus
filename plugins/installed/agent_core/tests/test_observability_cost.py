"""Cost surfacing in the run viewer + insights dashboard."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase


def _run(**kw):
    from plugins.installed.agent_core.models import AgentRun

    defaults = {
        'agent_name': 'worker',
        'user_message': 'do a thing',
        'state': 'completed',
        'provider': 'openai',
        'model': 'gpt-4o-mini',
        'prompt_tokens': 1_000_000,
        'completion_tokens': 1_000_000,
        'tool_call_count': 2,
        'duration_ms': 1200,
    }
    defaults.update(kw)
    return AgentRun.objects.create(**defaults)


class RunCostMethodTests(TestCase):
    def test_estimated_cost_uses_pricing(self):
        run = _run()
        # gpt-4o-mini at 1M+1M tokens = $0.75.
        self.assertAlmostEqual(run.estimated_cost_usd, 0.75, places=4)

    def test_unknown_model_zero_cost(self):
        self.assertEqual(_run(model='something-else').estimated_cost_usd, 0.0)


class ObservabilityCostViewTests(TestCase):
    def setUp(self):
        _run()
        self.c = Client()
        self.c.force_login(
            get_user_model().objects.create_user(
                username='s', email='s@x.test', password='pw', is_staff=True
            )
        )

    def test_insights_page_shows_cost(self):
        r = self.c.get('/dashboard/agents/observability/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Est. cost')
        self.assertContains(r, '$0.75')  # total cost KPI

    def test_run_detail_shows_cost(self):
        run = _run()
        r = self.c.get(f'/dashboard/agents/{run.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '$')


class ToolReliabilityViewTests(TestCase):
    def setUp(self):
        from plugins.installed.agent_core.models import AgentStep

        run = _run(state='completed', duration_ms=900)
        # 2 tool calls; one of the results failed.
        AgentStep.objects.create(run=run, seq=1, kind='tool_call', name='catalog.find')
        AgentStep.objects.create(
            run=run, seq=2, kind='tool_result', name='catalog.find', metadata={}
        )
        AgentStep.objects.create(run=run, seq=3, kind='tool_call', name='orders.refund')
        AgentStep.objects.create(
            run=run, seq=4, kind='tool_result', name='orders.refund', metadata={'failed': True}
        )
        from django.contrib.auth import get_user_model

        self.c = Client()
        self.c.force_login(
            get_user_model().objects.create_user(
                username='r', email='r@x.test', password='pw', is_staff=True
            )
        )

    def test_insights_shows_tool_success_and_failing_tools(self):
        r = self.c.get('/dashboard/agents/observability/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Tool success')
        self.assertContains(r, '50.0%')  # (2 calls - 1 fail) / 2
        self.assertContains(r, 'p95 latency')
        self.assertContains(r, 'orders.refund')  # failing tool listed
