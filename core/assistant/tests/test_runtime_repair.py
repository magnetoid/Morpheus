"""Phase 1b — runtime self-correction: JSON-repair of bad tool args + replan nudge."""

from __future__ import annotations

from dataclasses import dataclass

from django.test import TestCase

from core.assistant import Assistant
from core.assistant._mock_provider import _Resp
from core.assistant.tools.filesystem import ToolError, ToolResult, tool


@dataclass
class _TC:
    """A scripted tool call (matches the attrs the runtime reads)."""

    name: str
    arguments: dict
    id: str = 'tc1'


@tool(
    name='echo.x',
    description='echo the integer x',
    schema={'type': 'object', 'properties': {'x': {'type': 'integer'}}, 'required': ['x']},
)
def _echo_x(*, x: int) -> ToolResult:
    return ToolResult(output={'x': x})


@tool(name='always.fail', description='always raises', schema={'type': 'object', 'properties': {}})
def _always_fail() -> ToolResult:
    raise ToolError('boom — intentional failure')


class _RepairProvider:
    """Turn 1 emits a tool call with BAD args; the repair re-ask returns good
    args; the next turn returns final text."""

    name = 'repair'
    model = 'repair'

    def __init__(self):
        self.repaired = False
        self.emitted_tool = False

    def respond(self, *, messages, tools=None, temperature=0.3, max_tokens=1024):
        last_user = next(
            (m.content for m in reversed(messages or []) if getattr(m, 'role', '') == 'user'), ''
        )
        if 'corrected JSON arguments' in last_user:
            self.repaired = True
            return _Resp(text='{"x": 7}')
        if not self.emitted_tool:
            self.emitted_tool = True
            return _Resp(text='', tool_calls=[_TC('echo.x', {'y': 1})])  # missing required x
        return _Resp(text='done')


class _NudgeProvider:
    """Keeps calling a failing tool until it sees the replan nudge, then stops."""

    name = 'nudge'
    model = 'nudge'

    def __init__(self):
        self.seen_nudge = False
        self.calls = 0

    def respond(self, *, messages, tools=None, temperature=0.3, max_tokens=1024):
        for m in messages or []:
            if getattr(m, 'role', '') == 'system' and 'failed in a row' in (
                getattr(m, 'content', '') or ''
            ):
                self.seen_nudge = True
        self.calls += 1
        if self.seen_nudge or self.calls > 5:
            return _Resp(text='replanning')
        return _Resp(text='', tool_calls=[_TC('always.fail', {})])


class RuntimeRepairTests(TestCase):
    def test_bad_tool_args_are_repaired(self):
        prov = _RepairProvider()
        a = Assistant(provider=prov, tools=[_echo_x])
        result = a.run(message='echo seven', conversation_key='t:repair')
        self.assertTrue(prov.repaired, 'repair re-ask should have fired')
        self.assertEqual(result.state, 'completed')
        # The tool ran with the repaired args — its output is in the stored transcript.
        outputs = [
            m.tool_output
            for m in a.store.history(conversation_key='t:repair', limit=20)
            if getattr(m, 'role', '') == 'tool'
        ]
        self.assertIn({'x': 7}, outputs)


class RuntimeReplanTests(TestCase):
    def test_replan_nudge_after_two_consecutive_failures(self):
        prov = _NudgeProvider()
        a = Assistant(provider=prov, tools=[_always_fail])
        result = a.run(message='do the thing', conversation_key='t:nudge')
        self.assertTrue(prov.seen_nudge, 'a replan nudge should be injected after 2 failures')
        self.assertEqual(result.state, 'completed')
