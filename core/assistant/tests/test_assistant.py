"""Tests for Linda — the hard-coded staff AI assistant."""

# Lazy imports inside test methods are intentional (load-order isolation).
# ruff: noqa: PLC0415
from __future__ import annotations

from django.test import TestCase

from core.assistant import Assistant, get_default_tools


class AssistantBootTests(TestCase):
    def test_assistant_constructs_without_plugins(self):
        self.assertIsNotNone(Assistant().store)

    def test_default_tools_loaded(self):
        names = {t.name for t in get_default_tools()}
        # Representative spread of the post-pivot curated catalog (2026-05-23:
        # collapsed to one generic worker; raw fs.* / plugins.list / server_info
        # are intentionally NOT in Linda's default toolset).
        for required in (
            'db.list_models',
            'orders.search',
            'products.search',
            'run_python',
            'memory.recall',
            'delegate.list_agents',
            'delegate.invoke_agent',
        ):
            self.assertIn(required, names)


class AssistantTurnTests(TestCase):
    """One turn on the Janus engine, with the engine mocked (no model call)."""

    def _turn(self, payload, key):
        from unittest import mock

        with (
            mock.patch('core.assistant.janus_engine.janus_available', return_value=True),
            mock.patch(
                'core.assistant.janus_engine.iter_janus_turn',
                side_effect=lambda **kw: iter([payload]),
            ),
        ):
            events = list(Assistant().stream(message='hi', conversation_key=key))
        return events[-1]

    def test_completed_turn_is_stored(self):
        from core.assistant.persistence import get_default_store

        final = self._turn({'text': 'hello', 'error': '', 'duration_ms': 5}, 'test:turn')
        self.assertEqual((final['type'], final['result'].state), ('final', 'completed'))
        rows = get_default_store().history(conversation_key='test:turn')
        self.assertEqual(
            [(r.role, r.content) for r in rows], [('user', 'hi'), ('assistant', 'hello')]
        )

    def test_engine_error_becomes_a_friendly_failed_turn(self):
        final = self._turn({'text': '', 'error': 'janus exit 1', 'duration_ms': 5}, 'test:err')
        self.assertEqual((final['type'], final['result'].state), ('error', 'failed'))
        self.assertEqual(final['result'].error, 'janus exit 1')

    def test_missing_engine_is_reported_not_raised(self):
        from unittest import mock

        with mock.patch('core.assistant.janus_engine.janus_available', return_value=False):
            final = list(Assistant().stream(message='hi', conversation_key='test:none'))[-1]
        self.assertEqual(final['result'].error, 'janus_unavailable')
        self.assertIn("isn't installed", final['result'].text)


class AssistantStreamTests(TestCase):
    """What the chat receives while a turn runs, and what the reply records."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(
            username='ana', email='a@x.com', password='x', is_staff=True
        )

    def _stream(self, fake, key='t:stream', **context):
        from unittest import mock

        with (
            mock.patch('core.assistant.janus_engine.janus_available', return_value=True),
            mock.patch('core.assistant.janus_engine.iter_janus_turn', side_effect=fake),
        ):
            return list(
                Assistant().stream(
                    message='hi', conversation_key=key, context={'user': self.user, **context}
                )
            )

    def test_tool_calls_reach_the_chat_while_the_turn_runs(self):
        from core.assistant.persistence import StoredMessage, get_default_store

        def fake(**kw):
            yield None
            get_default_store().append(
                conversation_key='t:stream',
                message=StoredMessage(
                    role='tool',
                    tool_name='orders.search',
                    tool_args={'q': 'x'},
                    tool_output={'total': 3},
                ),
            )
            yield None
            yield {'text': 'Three orders.', 'error': '', 'duration_ms': 5}

        events = self._stream(fake)
        types = [e['type'] for e in events]
        self.assertEqual(types[0], 'progress')
        self.assertNotIn({'type': 'assistant_text', 'text': ''}, events)
        started = next(e for e in events if e['type'] == 'tool_call_started')
        finished = next(e for e in events if e['type'] == 'tool_call_finished')
        self.assertEqual((started['name'], finished['output']), ('orders.search', {'total': 3}))
        self.assertEqual(events[-1]['result'].tool_call_count, 1)

    def test_steps_and_the_plan_reach_the_chat(self):
        plan = {'type': 'plan', 'items': [{'id': '1', 'text': 'Check stock', 'status': 'pending'}]}
        step = {'type': 'step', 'id': 's1', 'state': 'running', 'label': 'Searching the web'}

        def fake(**kw):
            yield plan
            yield None
            yield step
            yield {'text': 'Done.', 'error': '', 'duration_ms': 5}

        events = self._stream(fake)
        self.assertIn(plan, events)
        self.assertIn(step, events)
        self.assertEqual(events[-1]['result'].text, 'Done.')
        # A step is not a message: the stored conversation stays question + answer.
        from core.assistant.persistence import get_default_store

        rows = get_default_store().history(conversation_key='t:stream')
        self.assertEqual([r.role for r in rows], ['user', 'assistant'])

    def test_the_prompt_teaches_only_the_janus_tools_the_turn_has(self):
        from unittest import mock

        from core.assistant import janus_settings

        prompt = Assistant()._system_prompt(context={})
        for tool in ('todo', 'web_search', 'session_search'):
            self.assertIn(f'`{tool}`', prompt)
        with mock.patch.object(janus_settings, 'web_search_enabled', return_value=False):
            prompt = Assistant()._system_prompt(context={})
        self.assertNotIn('web_search', prompt)
        self.assertIn('`todo`', prompt)

    def test_the_reply_records_tokens_and_counts_toward_the_spend_cap(self):
        from core.agents.guardrails import daily_spend_usd
        from core.assistant.models import AssistantConversation

        usage = {
            'input_tokens': 9000,
            'cache_read_tokens': 1000,
            'output_tokens': 400,
            'model': 'deepseek-v4-pro',
        }

        def fake(**kw):
            yield {'text': 'ok', 'error': '', 'duration_ms': 5, 'usage': usage}

        before = daily_spend_usd()
        final = self._stream(fake)[-1]['result']
        self.assertEqual((final.prompt_tokens, final.completion_tokens), (10000, 400))
        summary = AssistantConversation.objects.get(key='t:stream').cost_summary()
        self.assertEqual(summary['total_tokens'], 10400)
        self.assertGreater(daily_spend_usd(), before)

    def test_the_system_prompt_stays_the_same_between_messages(self):
        # Janus puts it ahead of the transcript; a prompt that changes every
        # message makes the provider re-read the whole conversation uncached.
        seen = []

        def fake(**kw):
            seen.append(kw)
            yield {'text': 'ok', 'error': '', 'duration_ms': 5}

        self._stream(fake, page_url='/dashboard/orders/', page_title='Orders')
        self._stream(fake, page_url='/dashboard/products/', page_title='Products')
        self.assertEqual(seen[0]['system_prompt'], seen[1]['system_prompt'])
        self.assertIn('/dashboard/orders/', seen[0]['turn_context'])
        self.assertIn('/dashboard/products/', seen[1]['turn_context'])
        self.assertIn('hi', seen[1]['history'])  # the first message, for a fresh session


class ToolMigrationTests(TestCase):
    """D3: orders.search / orders.get moved to the orders plugin but stay in
    Linda's catalogue under the same names (sourced from the agent registry)."""

    MIGRATED = [
        'orders.search',
        'orders.get',
        'products.search',
        'products.get',
        'customers.search',
        'customers.get',
        'media.search',
        'metafields.list_for',
        'markets.list',
        'analytics.summary',
        'analytics.top_products',
        'cms.pages',
        'email.templates',
    ]

    def test_read_tools_contributed_by_their_plugins(self):
        from plugins.installed.catalog.app import CatalogPlugin
        from plugins.installed.customers.app import CustomersPlugin
        from plugins.installed.orders.app import OrdersPlugin

        self.assertGreaterEqual(
            {t.name for t in OrdersPlugin().contribute_agent_tools()},
            {'orders.search', 'orders.get'},
        )
        self.assertGreaterEqual(
            {t.name for t in CatalogPlugin().contribute_agent_tools()},
            {'products.search', 'products.get'},
        )
        self.assertGreaterEqual(
            {t.name for t in CustomersPlugin().contribute_agent_tools()},
            {'customers.search', 'customers.get'},
        )

    def test_linda_still_exposes_migrated_tools_by_name(self):
        names = {t.name for t in get_default_tools()}
        for n in self.MIGRATED:
            self.assertIn(n, names)

    def test_not_imported_from_core_ecommerce_anymore(self):
        import core.assistant.tools.ecommerce as ec

        for sym in (
            'orders_search_tool',
            'orders_get_tool',
            'products_search_tool',
            'products_get_tool',
            'customers_search_tool',
            'customers_get_tool',
            'media_search_tool',
            'metafields_list_for_tool',
            'markets_list_tool',
        ):
            self.assertFalse(hasattr(ec, sym), sym)

    def test_migrated_orders_search_queries_real_orders(self):
        tool = next(t for t in get_default_tools() if t.name == 'orders.search')
        result = tool.invoke({'limit': 5})
        self.assertIn('orders', result.output)
        self.assertIsInstance(result.output['orders'], list)


class FilesystemToolTests(TestCase):
    def test_list_dir_returns_entries(self):
        from core.assistant.tools.filesystem import list_dir_tool

        result = list_dir_tool.invoke({'path': '.'})
        self.assertIn('entries', result.output)
        self.assertGreater(len(result.output['entries']), 0)

    def test_path_traversal_rejected(self):
        from core.assistant.tools.filesystem import ToolError, read_file_tool

        with self.assertRaises(ToolError):
            read_file_tool.invoke({'path': '../../../etc/passwd'})


class FallbackStoreTests(TestCase):
    def test_file_history_round_trip(self, tmp_path=None):
        import os
        import tempfile

        from core.assistant.persistence import AssistantStore, StoredMessage

        os.environ['MORPHEUS_ASSISTANT_FALLBACK'] = tempfile.mkdtemp()
        store = AssistantStore(prefer_db=False)
        store.append(conversation_key='k1', message=StoredMessage(role='user', content='ping'))
        store.append(conversation_key='k1', message=StoredMessage(role='assistant', content='pong'))
        rows = store.history(conversation_key='k1', limit=10)
        self.assertEqual([r.role for r in rows], ['user', 'assistant'])
        self.assertEqual(rows[0].content, 'ping')
