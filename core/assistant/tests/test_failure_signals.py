"""Linda's failures surface as self-improvement signals."""

from __future__ import annotations

from unittest import mock

from django.test import TestCase

from core.assistant import Assistant
from core.self_improvement.models import SiSignal


def _turn(key, *, available=True, payload=None):
    with (
        mock.patch('core.assistant.janus_engine.janus_available', return_value=available),
        mock.patch(
            'core.assistant.janus_engine.iter_janus_turn',
            side_effect=lambda **kw: iter(
                [payload or {'text': '', 'error': 'janus exit 1', 'duration_ms': 1}]
            ),
        ),
    ):
        list(Assistant().stream(message='hi', conversation_key=key))


class FailureSignalTests(TestCase):
    def test_engine_failure_emits_signal(self):
        _turn('t:engine')
        self.assertTrue(
            SiSignal.objects.filter(
                source='agent_failure', fingerprint='assistant:janus_engine_error'
            ).exists()
        )

    def test_missing_engine_emits_signal(self):
        _turn('t:missing', available=False)
        self.assertTrue(SiSignal.objects.filter(fingerprint='assistant:janus_unavailable').exists())

    def test_completed_turn_emits_nothing(self):
        _turn('t:ok', payload={'text': 'fine', 'error': '', 'duration_ms': 1})
        self.assertFalse(SiSignal.objects.filter(source='agent_failure').exists())

    def test_signals_dedup_by_reason(self):
        for i in range(2):
            _turn(f't:dedup{i}')
        self.assertEqual(
            SiSignal.objects.filter(fingerprint='assistant:janus_engine_error').count(), 1
        )
