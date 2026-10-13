"""Shop memory: Morpheus's facts about THIS store, kept apart from Janus's own learning.

Janus is a general open-source agent with its own generic learning (JanusLearning).
What the assistant should always know about the specific store it runs in — its
positioning, the merchant's preferences — is Morpheus's layer, the shop memory.
It is injected into every turn, a superadmin curates it, and Janus may propose a
fact that is saved only when the merchant's own message confirms it. The old
generic reflection flywheel (tool gaps and workflow lessons written into the
store's memory) is gone: that was Janus's job, and it polluted the shop facts.
"""

from __future__ import annotations

from unittest import mock

from django.test import TestCase

from core.assistant.models import LindaMemory


class ShopMemoryReachTests(TestCase):
    def _linda_names(self):
        import types

        from plugins.installed.agent_mcp.linda_turn import LindaTurn, catalogue

        user = types.SimpleNamespace(is_staff=True, is_superuser=False, pk=1)
        turn = LindaTurn(user=user, conversation_key='user:1:chat:s', mode_slug='general')
        return {t.name: t for t in catalogue(turn)}

    def test_janus_can_read_and_propose_shop_facts(self):
        names = self._linda_names()
        self.assertIn('memory.recall', names)
        self.assertIn('memory.remember', names)

    def test_saving_a_shop_fact_needs_the_merchants_own_yes(self):
        from plugins.installed.agent_mcp.linda_turn import needs_consent

        names = self._linda_names()
        self.assertTrue(needs_consent(names['memory.remember']))
        self.assertTrue(needs_consent(names['memory.forget']))
        self.assertFalse(needs_consent(names['memory.recall']))


class ShopMemoryInjectionTests(TestCase):
    def test_the_turn_is_told_these_are_facts_about_this_store(self):
        from core.assistant.runtime import _format_recent_memories

        LindaMemory.objects.create(
            scope='merchant', key='store_type', value='A Montenegro marketplace'
        )
        text = _format_recent_memories('anything')
        self.assertIn('THIS STORE', text.upper())
        self.assertIn('A Montenegro marketplace', text)


class NoGenericFlywheelTests(TestCase):
    """Reflection judges a Worker run and updates skill counters, nothing more."""

    def _run(self, payload):
        from core.assistant.reflection import reflect_on_worker_run

        class _Run:
            id = 'r1'
            user_message = 'audit SEO'
            state = 'completed'
            error = ''
            final_text = 'done'
            metadata = {'skills': []}

        provider = mock.Mock(name='provider')
        provider.name = 'openai'
        provider.respond.return_value = mock.Mock(text=payload)
        return reflect_on_worker_run(_Run(), provider=provider)

    def test_lessons_and_tool_gaps_are_not_written_into_shop_memory(self):
        payload = (
            '{"outcome": "success",'
            ' "lessons": [{"key": "profile_orm_queries_early", "value": "aggregate queries"}],'
            ' "tool_gaps": ["a generic db query tool"]}'
        )
        self._run(payload)
        self.assertFalse(LindaMemory.objects.exists())
