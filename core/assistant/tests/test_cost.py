"""Per-conversation cost tracking on Linda's chat."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from core.assistant.models import AssistantConversation, AssistantMessage
from core.assistant.persistence import AssistantStore, StoredMessage


class CostSummaryTests(TestCase):
    def test_sums_tokens_and_prices_by_model(self):
        conv = AssistantConversation.objects.create(key='user:1')
        AssistantMessage.objects.create(
            conversation=conv,
            role='assistant',
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            model='gpt-4o-mini',
        )
        s = conv.cost_summary()
        self.assertEqual(s['total_tokens'], 2_000_000)
        self.assertAlmostEqual(s['cost_usd'], 0.75, places=4)  # 0.15 in + 0.60 out

    def test_unknown_model_is_zero_cost(self):
        conv = AssistantConversation.objects.create(key='user:2')
        AssistantMessage.objects.create(
            conversation=conv,
            role='assistant',
            prompt_tokens=500,
            completion_tokens=500,
            model='mystery',
        )
        self.assertEqual(conv.cost_summary()['cost_usd'], 0.0)

    def test_empty_conversation(self):
        conv = AssistantConversation.objects.create(key='user:3')
        self.assertEqual(conv.cost_summary()['total_tokens'], 0)


class PersistenceTokenTests(TestCase):
    def test_store_persists_tokens(self):
        AssistantStore(prefer_db=True).append(
            conversation_key='user:9',
            message=StoredMessage(
                role='assistant',
                content='hi',
                prompt_tokens=120,
                completion_tokens=40,
                model='gpt-4o-mini',
            ),
        )
        msg = AssistantConversation.objects.get(key='user:9').messages.first()
        self.assertEqual(msg.prompt_tokens, 120)
        self.assertEqual(msg.completion_tokens, 40)
        self.assertEqual(msg.model, 'gpt-4o-mini')


class HistoryEndpointTests(TestCase):
    def test_history_includes_cost_summary(self):
        c = Client()
        c.force_login(
            get_user_model().objects.create_user(
                username='s', email='s@x.test', password='pw', is_staff=True
            )
        )
        r = c.get('/dashboard/assistant/history/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('summary', r.json())
