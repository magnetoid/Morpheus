"""Linda's work is visible where the merchant looks for it.

Observability aggregated only Worker runs (a Janus-only store showed "No runs"
against 42 replies a week), Activity never showed a refused write (Irving had
83 in a week), and the AI-Act export — "the trail of human approvals" — left out
every one of Linda's consents and refusals.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from core.agents.models import AgentRun
from core.audit.models import AuditEvent


def _refusal(tool='catalog__update', reason='needs consent: the merchant has not said yes'):
    return AuditEvent.objects.create(
        event_type='mcp.tool_denied',
        severity='warning',
        actor_label='mcp:linda:user-1',
        target=f'tool/{tool}',
        metadata={'reason': reason},
    )


class ObservabilityShowsLindaTests(TestCase):
    def setUp(self):
        self.c = Client()
        self.c.force_login(
            get_user_model().objects.create_user(
                username='obs', email='obs@x.test', password='pw', is_staff=True
            )
        )

    def test_linda_runs_and_refusals_appear(self):
        AgentRun.objects.create(
            agent_name='linda',
            user_message='hi',
            final_text='ok',
            state='completed',
            provider='deepseek',
            model='deepseek-chat',
            prompt_tokens=1000,
            completion_tokens=100,
            duration_ms=1200,
        )
        _refusal()
        r = self.c.get('/dashboard/agents/observability/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual([row['agent_name'] for row in r.context['by_agent']], ['linda'])
        self.assertEqual(r.context['refusals'], 1)
        self.assertContains(r, 'Refused writes')


class ActivityShowsRefusalsTests(TestCase):
    def test_a_refused_write_is_a_row(self):
        from plugins.installed.agent_core.views import _janus_activity_log

        _refusal()
        feed = _janus_activity_log()
        refused = [e for e in feed['events'] if e['kind'] == 'refused']
        self.assertEqual(len(refused), 1)
        self.assertIn('catalog__update', refused[0]['text'])
        self.assertIn('needs consent', refused[0]['text'])
        self.assertEqual(feed['refused'], 1)


class AiActConsentTrailTests(TestCase):
    def _write(self, error, tool='catalog__update'):
        return AuditEvent.objects.create(
            event_type='assistant.tool_write',
            severity='warning' if error else 'info',
            actor_label='owner@x.test',
            target=f'tool/{tool}',
            metadata={'tool': tool, 'error': error, 'conversation': 'user:1'},
        )

    def test_consents_and_refusals_are_exported(self):
        from plugins.installed.agent_core.compliance import build_ai_act_report

        self._write('needs consent: the merchant has not said yes')
        self._write('')
        _refusal(tool='orders__refund', reason='scope')
        r = build_ai_act_report()
        self.assertEqual(r['summary']['total_consents'], 1)
        self.assertEqual(r['summary']['total_refusals'], 2)
        self.assertEqual(
            sorted(c['outcome'] for c in r['consents']), ['executed', 'refused', 'refused']
        )
        for row in r['consents']:
            self.assertTrue(row['timestamp'] and row['tool'] and row['actor'])

    def test_the_window_applies(self):
        from django.utils import timezone

        from plugins.installed.agent_core.compliance import build_ai_act_report

        self._write('')
        r = build_ai_act_report(since=timezone.now() + timezone.timedelta(days=1))
        self.assertEqual(r['summary']['total_consents'], 0)
