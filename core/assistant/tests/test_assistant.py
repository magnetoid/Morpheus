"""Tests for Linda — the hard-coded staff AI assistant."""

# Lazy imports inside test methods are intentional (load-order isolation).
# ruff: noqa: PLC0415
from __future__ import annotations

from django.test import TestCase

from core.assistant import Assistant, get_default_tools
from core.assistant._mock_provider import MockAssistantProvider


class AssistantBootTests(TestCase):
    def test_assistant_constructs_without_plugins(self):
        a = Assistant(provider=MockAssistantProvider())
        self.assertEqual(a.name, 'assistant')

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


class AssistantRunTests(TestCase):
    def test_run_returns_completed_with_mock_provider(self):
        a = Assistant(provider=MockAssistantProvider(), tools=[])
        result = a.run(message='hi', conversation_key='test:1')
        self.assertEqual(result.state, 'completed')
        self.assertIn('hi', result.text)

    def test_provider_failure_marks_failed(self):
        class _Boom:
            def respond(self, **kw):
                raise RuntimeError('provider down')

        a = Assistant(provider=_Boom(), tools=[])
        result = a.run(message='hi', conversation_key='test:2')
        self.assertEqual(result.state, 'failed')
        self.assertIn('provider down', result.error)

    def test_degraded_sentinel_becomes_friendly_error_not_an_answer(self):
        # Regression (prod, 2026-07-12): the fallback router returns
        # "[All AI providers degraded. Last error: …]" as response TEXT, and
        # Linda shipped it into the chat verbatim as a completed answer. It
        # must fail the turn with the friendly provider-error copy instead.
        from core.agents.llm import LLMResponse

        class _Degraded:
            def respond(self, **kw):
                return LLMResponse(
                    text='[All AI providers degraded. Last error: anthropic: '
                    'Could not resolve authentication method. Expected one of '
                    'api_key, auth_token, or credentials to be set.]',
                    model='fallback_router_failed',
                )

        a = Assistant(provider=_Degraded(), tools=[])
        result = a.run(message='can you send emails?', conversation_key='test:degraded')
        self.assertEqual(result.state, 'failed')
        self.assertNotIn('[All AI providers degraded', result.text)
        self.assertIn('/dashboard/settings/ai/', result.text)
        # The persisted assistant message is the friendly copy too — history
        # replays must not resurface the raw sentinel.
        history = a.store.history(conversation_key='test:degraded', limit=10)
        stored = [m.content for m in history if m.role == 'assistant']
        self.assertTrue(stored and '[All AI providers degraded' not in stored[-1])

    def test_history_persists(self):
        a = Assistant(provider=MockAssistantProvider(), tools=[])
        a.run(message='first', conversation_key='test:hist')
        a.run(message='second', conversation_key='test:hist')
        history = a.store.history(conversation_key='test:hist', limit=10)
        roles = [m.role for m in history]
        self.assertIn('user', roles)
        self.assertIn('assistant', roles)
        self.assertEqual(roles.count('user'), 2)


class _RecordingProvider:
    """Records the message list passed to each respond() call."""

    name = 'rec'
    model = 'rec'

    def __init__(self):
        self.calls: list = []

    def respond(self, *, messages, tools=None, temperature=0.3, max_tokens=1024):
        from core.assistant._mock_provider import _Resp

        self.calls.append(list(messages))
        return _Resp(text='ok')


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
        from plugins.installed.catalog.plugin import CatalogPlugin
        from plugins.installed.customers.plugin import CustomersPlugin
        from plugins.installed.orders.plugin import OrdersPlugin

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


class HistoryCompactionTests(TestCase):
    def test_summarize_history_returns_provider_text(self):
        a = Assistant(provider=MockAssistantProvider(), tools=[])
        out = a._summarize_history('user: hi\nassistant: hello')
        self.assertIn('Got:', out)  # MockAssistantProvider echoes the transcript

    def test_long_history_is_compacted_before_the_provider_call(self):
        from core.assistant.persistence import StoredMessage

        prov = _RecordingProvider()
        a = Assistant(provider=prov, tools=[])
        key = 'test:compact'
        # Seed a history that comfortably exceeds the ~6000-token soft limit
        # (10 messages × ~3000 chars ≈ 7.5k tokens).
        for i in range(10):
            a.store.append(
                conversation_key=key,
                message=StoredMessage(
                    role='user' if i % 2 == 0 else 'assistant', content='x' * 3000
                ),
            )
        a.run(message='now', conversation_key=key)

        # The actual turn call (the one carrying the recent 'now' message) must
        # be compacted: a rolling-summary system message replaces the old middle.
        turn_calls = [
            ms for ms in prov.calls if any(getattr(m, 'content', '') == 'now' for m in ms)
        ]
        self.assertTrue(turn_calls, 'no turn call recorded')
        turn = turn_calls[-1]
        self.assertTrue(
            any(
                'Summary of earlier conversation' in (getattr(m, 'content', '') or '') for m in turn
            ),
            'expected a rolling summary in the compacted turn',
        )
        # And it is shorter than the raw history would have been (10 + system + user).
        self.assertLess(len(turn), 12)


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
