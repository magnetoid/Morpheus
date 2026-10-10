"""Automations run on Linda (Janus) — Automations is the store's cron.

Owner's ask (2026-10-10): "automations is cron … integrate cron with
Automations, choose the best way". Automations stays the one scheduler (rows
in the database, so a redeploy loses nothing); a Linda automation runs as a
Linda turn for its owner, in its own conversation (listed under Chats), and
its last report is kept on the row. It may read and report, never approve a
change (see core/assistant/tests/test_automation_consent.py).
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.assistant.models import AssistantConversation
from plugins.installed.agent_core.models import BackgroundAgent


class _Result:
    def __init__(self, text, error=''):
        self.text, self.error, self.state = text, error, 'failed' if error else 'completed'


class _FakeAssistant:
    calls: list[dict] = []
    answer = 'Stock is fine. Two products are close to their reorder point.'

    def stream(self, *, message, conversation_key, context):
        type(self).calls.append({'message': message, 'key': conversation_key, 'context': context})
        yield {'type': 'final', 'result': _Result(type(self).answer)}


class LindaAutomationTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username='auto-owner', email='auto@x.io', password='pw', is_staff=True,
            is_superuser=True,
        )  # fmt: skip
        _FakeAssistant.calls = []
        patcher = mock.patch(
            'plugins.installed.agent_core.linda_automations.Assistant', _FakeAssistant
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _job(self, **fields):
        defaults = {
            'name': 'Morning stock check',
            'agent_name': 'worker',
            'engine': BackgroundAgent.ENGINE_LINDA,
            'prompt': 'Check stock and tell me what is running low.',
            'created_by': self.owner,
        }
        return BackgroundAgent.objects.create(**{**defaults, **fields})

    def test_a_run_is_a_linda_turn_in_its_own_chat_and_keeps_the_report(self):
        from core.assistant import gates
        from plugins.installed.agent_core.scheduler import fire

        job = self._job()
        fire(job)
        job.refresh_from_db()
        self.assertEqual(job.last_output, _FakeAssistant.answer)
        self.assertEqual(job.last_error, '')
        call = _FakeAssistant.calls[0]
        self.assertEqual(call['key'], gates.automation_key(self.owner.pk, job.pk))
        self.assertEqual(call['context']['user'], self.owner)
        self.assertTrue(call['context']['mcp_public'])
        self.assertIn('Check stock', call['message'])
        chat = AssistantConversation.objects.get(key=call['key'])
        self.assertEqual(chat.user, self.owner)
        self.assertIn('Morning stock check', chat.title)

    def test_an_automation_without_an_owner_does_not_run(self):
        from plugins.installed.agent_core.scheduler import fire

        job = self._job(created_by=None)
        fire(job)
        job.refresh_from_db()
        self.assertEqual(_FakeAssistant.calls, [])
        self.assertIn('owner', job.last_error)

    def test_daily_at_schedules_the_next_occurrence_in_the_store_timezone(self):
        from plugins.installed.agent_core.scheduler import schedule_next

        job = self._job(daily_at=time(7, 30))
        schedule_next(job)
        local = job.next_run_at.astimezone(ZoneInfo(settings.TIME_ZONE))
        self.assertEqual((local.hour, local.minute), (7, 30))
        self.assertGreater(job.next_run_at, timezone.now())
        self.assertLessEqual(job.next_run_at - timezone.now(), timedelta(days=1))
        self.assertIsInstance(local, datetime)

    def test_the_page_creates_a_linda_automation(self):
        self.client.force_login(self.owner)
        self.client.post(
            '/dashboard/agents/background/',
            {
                'name': 'Weekly SEO look',
                'engine': 'linda',
                'prompt': 'Which product pages miss a description?',
                'daily_at': '08:15',
                'interval_seconds': '3600',
            },
        )
        job = BackgroundAgent.objects.get(name='Weekly SEO look')
        self.assertEqual(job.engine, BackgroundAgent.ENGINE_LINDA)
        self.assertEqual(job.daily_at, time(8, 15))
        self.assertEqual(job.created_by, self.owner)


class PublicMcpEndpointTests(TestCase):
    def test_a_turn_without_a_request_reaches_the_store_by_its_public_address(self):
        from core.assistant import janus_engine as eng

        with mock.patch.object(eng, '_default_host', return_value='shop.example'):
            url, headers = eng._mcp_endpoint({'mcp_public': True})
        self.assertEqual(url, 'https://shop.example/mcp/admin/v1/')
        self.assertEqual(headers, {})
