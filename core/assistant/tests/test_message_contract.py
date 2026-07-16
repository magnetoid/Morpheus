"""Provider message-contract safety (the DeepSeek 400 incident, 2026-07-16).

OpenAI-compatible APIs require a role='tool' message to directly follow the
assistant message carrying its matching tool_calls. Two Morpheus paths could
emit dangling tool messages and 400 every strict provider ("All AI providers
degraded"):

  1. History replay — the store never persisted tool_call ids, so a continued
     conversation whose history contained tool use replayed
     assistant(plain) → tool(no id). Fixed: tool history folds into an
     assistant-text record.
  2. Compaction — the keep-recent index cut could land between the assistant
     tool_calls message and its tool results, orphaning them. Fixed: the
     boundary shifts so pairs stay in the summarized middle.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from core.agents.compaction import compact
from core.agents.llm import LLMMessage, LLMToolCall
from core.assistant.persistence import StoredMessage
from core.assistant.runtime import _to_llm_messages


def _assert_contract(msgs, testcase):
    """Every role='tool' message must directly follow a message with
    tool_calls (the strict-provider rule this file guards)."""
    for i, m in enumerate(msgs):
        if getattr(m, 'role', '') == 'tool':
            testcase.assertGreater(i, 0, 'tool message first in list')
            prev = msgs[i - 1]
            testcase.assertTrue(
                getattr(prev, 'tool_calls', None) or getattr(prev, 'role', '') == 'tool',
                f'dangling tool message at index {i}',
            )


class ReplayContractTests(SimpleTestCase):
    def test_replayed_tool_history_never_emits_tool_role(self):
        history = [
            StoredMessage(role='user', content='how many orders today?'),
            StoredMessage(role='assistant', content='let me check'),
            StoredMessage(role='tool', tool_name='orders.search', tool_output={'count': 3}),
            StoredMessage(role='assistant', content='3 orders today.'),
        ]
        msgs = _to_llm_messages(history, 'and yesterday?')
        self.assertNotIn('tool', [m.role for m in msgs])
        _assert_contract(msgs, self)
        # The tool record survives as assistant-visible text (name + output).
        folded = [m for m in msgs if m.role == 'assistant' and 'orders.search' in (m.content or '')]
        self.assertEqual(len(folded), 1)
        self.assertIn('"count": 3', folded[0].content)


class CompactionContractTests(SimpleTestCase):
    def _convo_with_tool_pair_at_boundary(self, keep_recent):
        # Build: system + filler turns + [assistant(tool_calls), tool, tool]
        # positioned so the keep_recent cut lands INSIDE the pair.
        msgs = [LLMMessage(role='system', content='sys')]
        for i in range(6):
            msgs.append(LLMMessage(role='user', content=f'q{i} ' + 'x' * 200))
            msgs.append(LLMMessage(role='assistant', content=f'a{i} ' + 'y' * 200))
        msgs.append(
            LLMMessage(
                role='assistant',
                content='',
                tool_calls=[LLMToolCall(id='c1', name='t', arguments={})],
            )
        )
        msgs.append(LLMMessage(role='tool', tool_call_id='c1', name='t', content='{"r": 1}'))
        msgs.append(LLMMessage(role='tool', tool_call_id='c1', name='t', content='{"r": 2}'))
        for i in range(keep_recent - 2):
            msgs.append(LLMMessage(role='user', content=f'tail{i}'))
        return msgs

    def test_boundary_never_orphans_tool_messages(self):
        keep = 4
        msgs = self._convo_with_tool_pair_at_boundary(keep)
        # keep_recent=4 window would start with the two tool messages.
        out = compact(msgs, soft_limit=1, keep_recent=keep, summarizer=lambda t: 'summary')
        self.assertLess(len(out), len(msgs))  # it did compact
        _assert_contract(out, self)

    def test_truncation_fallback_also_safe(self):
        keep = 4
        msgs = self._convo_with_tool_pair_at_boundary(keep)
        out = compact(msgs, soft_limit=1, keep_recent=keep, summarizer=None)
        _assert_contract(out, self)
