"""Phase 1d — Linda's failures surface as self-improvement signals."""

from __future__ import annotations

from dataclasses import dataclass

from django.test import TestCase

from core.assistant import Assistant
from core.assistant._mock_provider import _Resp
from core.assistant.tools.filesystem import ToolResult, tool
from core.self_improvement.models import SiSignal


@dataclass
class _TC:
    name: str
    arguments: dict
    id: str = 'tc1'


@tool(name='noop.t', description='no-op', schema={'type': 'object', 'properties': {}})
def _noop() -> ToolResult:
    return ToolResult(output={'ok': True})


class _BoomProvider:
    name = 'boom'
    model = 'boom'

    def respond(self, *, messages, tools=None, temperature=0.3, max_tokens=1024):
        raise RuntimeError('provider down')


class _LoopProvider:
    """Always asks for a tool call → the run grinds to max_steps."""

    name = 'loop'
    model = 'loop'

    def respond(self, *, messages, tools=None, temperature=0.3, max_tokens=1024):
        return _Resp(text='', tool_calls=[_TC('noop.t', {})])


class FailureSignalTests(TestCase):
    def test_provider_failure_emits_signal(self):
        Assistant(provider=_BoomProvider(), tools=[]).run(
            message='hi', conversation_key='t:provfail'
        )
        self.assertTrue(
            SiSignal.objects.filter(
                source='agent_failure', fingerprint='assistant:provider_error'
            ).exists()
        )

    def test_max_steps_emits_signal(self):
        Assistant(provider=_LoopProvider(), tools=[_noop], max_steps=3).run(
            message='loop forever', conversation_key='t:maxsteps'
        )
        self.assertTrue(
            SiSignal.objects.filter(
                source='agent_failure', fingerprint='assistant:max_steps_exceeded'
            ).exists()
        )

    def test_signals_dedup_by_reason(self):
        # Two provider failures collapse to a single signal (emit_signal dedups).
        for i in range(2):
            Assistant(provider=_BoomProvider(), tools=[]).run(
                message='hi', conversation_key=f't:dedup{i}'
            )
        self.assertEqual(SiSignal.objects.filter(fingerprint='assistant:provider_error').count(), 1)
