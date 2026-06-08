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

    def test_history_persists(self):
        a = Assistant(provider=MockAssistantProvider(), tools=[])
        a.run(message='first', conversation_key='test:hist')
        a.run(message='second', conversation_key='test:hist')
        history = a.store.history(conversation_key='test:hist', limit=10)
        roles = [m.role for m in history]
        self.assertIn('user', roles)
        self.assertIn('assistant', roles)
        self.assertEqual(roles.count('user'), 2)


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
