"""Release 2 of docs/plans/linda-self-learning-2026-07.md — Linda's daily
briefing: opt-in beat task, read-only Worker run, home-panel payload."""

from __future__ import annotations

import json
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.agents.llm import LLMResponse, MockLLMProvider
from core.assistant.briefing import _read_only_worker, latest_briefing, run_daily_briefing
from core.assistant.models import AssistantBriefing
from core.models import StoreSettings


def _briefing_provider(payload: dict) -> MockLLMProvider:
    return MockLLMProvider(responses=[LLMResponse(text=json.dumps(payload))], echo_user=False)


def _enable(on: bool = True):
    s = StoreSettings.objects.first() or StoreSettings()
    s.ai_daily_briefing = on
    s.save()


class BriefingRunTests(TestCase):
    def test_disabled_skips_without_a_row(self):
        out = run_daily_briefing(provider=_briefing_provider({}))
        self.assertEqual(out, {'skipped': 'disabled'})
        self.assertEqual(AssistantBriefing.objects.count(), 0)

    def test_generates_and_parses_actions(self):
        _enable()
        provider = _briefing_provider(
            {
                'briefing': 'Revenue up 12% vs yesterday.\nTwo products are out of stock.',
                'actions': [
                    {
                        'label': 'Restock the two products',
                        'prompt': 'Which products are out of stock and what should I reorder?',
                    },
                ],
            }
        )
        out = run_daily_briefing(provider=provider)
        self.assertEqual(out['status'], 'ok')
        row = AssistantBriefing.objects.get()
        self.assertIn('Revenue up 12%', row.body)
        self.assertEqual(row.actions[0]['label'], 'Restock the two products')

    def test_idempotent_per_day(self):
        _enable()
        run_daily_briefing(provider=_briefing_provider({'briefing': 'quiet day', 'actions': []}))
        out = run_daily_briefing(provider=_briefing_provider({'briefing': 'again', 'actions': []}))
        self.assertEqual(out, {'skipped': 'already generated today'})
        self.assertEqual(AssistantBriefing.objects.count(), 1)

    def test_non_json_reply_keeps_raw_text(self):
        _enable()
        provider = MockLLMProvider(
            responses=[LLMResponse(text='Sales were steady; nothing urgent.')], echo_user=False
        )
        out = run_daily_briefing(provider=provider)
        self.assertEqual(out['status'], 'ok')
        row = AssistantBriefing.objects.get()
        self.assertEqual(row.body, 'Sales were steady; nothing urgent.')
        self.assertEqual(row.actions, [])

    def test_read_only_worker_has_no_write_scopes(self):
        clone = _read_only_worker()
        self.assertTrue(clone.scopes)
        bad = [s for s in clone.scopes if not s.endswith('.read')]
        self.assertEqual(bad, [])  # no *.write, no orders.cancel


class LatestBriefingTests(TestCase):
    def test_none_when_disabled(self):
        AssistantBriefing.objects.create(date=timezone.localdate(), body='hi')
        self.assertIsNone(latest_briefing())

    def test_returns_fresh_briefing(self):
        _enable()
        AssistantBriefing.objects.create(
            date=timezone.localdate(),
            body='hello',
            actions=[{'label': 'Do it', 'prompt': 'please do it'}, {'bogus': True}],
        )
        out = latest_briefing()
        self.assertEqual(out['body'], 'hello')
        self.assertEqual(len(out['actions']), 1)  # malformed action filtered

    def test_stale_briefing_hidden(self):
        _enable()
        AssistantBriefing.objects.create(date=timezone.localdate() - timedelta(days=5), body='old')
        self.assertIsNone(latest_briefing())

    def test_failed_briefing_hidden(self):
        _enable()
        AssistantBriefing.objects.create(date=timezone.localdate(), body='', status='failed')
        self.assertIsNone(latest_briefing())
