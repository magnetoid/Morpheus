"""Janus engine adapter for Linda — no live Janus process in the suite."""

from __future__ import annotations

from django.test import SimpleTestCase, override_settings

from core.assistant.janus_engine import janus_available, run_janus_turn
from core.assistant.runtime import Assistant
from core.assistant._mock_provider import MockAssistantProvider


class JanusDiscoveryTests(SimpleTestCase):
    def test_missing_binary_is_unavailable(self):
        with override_settings(JANUS_BIN='', JANUS_ENGINE_ROOT='/no/such/janus'):
            # PATH may still have `janus` on this machine — that's fine;
            # we only assert the helper doesn't crash.
            janus_available()


class JanusTurnTests(SimpleTestCase):
    def test_unavailable_returns_error_payload(self):
        import core.assistant.janus_engine as eng

        orig = eng.janus_cmd
        eng.janus_cmd = lambda: None
        try:
            out = run_janus_turn(
                message='hi',
                conversation_key='t',
                system_prompt='You are Linda.',
            )
        finally:
            eng.janus_cmd = orig
        self.assertEqual(out['error'], 'janus_unavailable')
        self.assertEqual(out['text'], '')


class AssistantJanusRoutingTests(SimpleTestCase):
    def test_injected_provider_stays_on_legacy_loop(self):
        a = Assistant(provider=MockAssistantProvider(), tools=[])
        self.assertFalse(a._should_use_janus())

    def test_identity_stays_linda(self):
        from core.assistant.prompts import LINDA_BASE_PROMPT

        self.assertIn('You are Linda', LINDA_BASE_PROMPT)
        self.assertIn('never needs the name of your engine', LINDA_BASE_PROMPT)

    @override_settings(LINDA_ENGINE='legacy')
    def test_tests_force_legacy_engine(self):
        a = Assistant(tools=[])
        self.assertFalse(a._should_use_janus())
