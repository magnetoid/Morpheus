"""Context-window compaction (`core/agents/compaction.py`)."""

from __future__ import annotations

from django.test import SimpleTestCase

from core.agents.compaction import DEFAULT_KEEP_RECENT, compact, estimate_tokens
from core.agents.llm import LLMMessage


def _msgs(n: int, *, chars: int = 2000, lead_system: bool = True):
    out = []
    if lead_system:
        out.append(LLMMessage(role='system', content='SYSTEM PROMPT'))
    for i in range(n):
        role = 'user' if i % 2 == 0 else 'assistant'
        out.append(LLMMessage(role=role, content=f'msg{i} ' + ('x' * chars)))
    return out


class EstimateTokensTests(SimpleTestCase):
    def test_scales_with_content(self):
        small = estimate_tokens([LLMMessage(role='user', content='x' * 40)])
        big = estimate_tokens([LLMMessage(role='user', content='x' * 4000)])
        self.assertLess(small, big)
        self.assertEqual(small, 10)  # 40 chars / 4


class CompactTests(SimpleTestCase):
    def test_short_history_is_unchanged(self):
        msgs = _msgs(4, chars=10)
        self.assertIs(compact(msgs, soft_limit=6000), msgs)

    def test_truncation_fallback_without_summarizer(self):
        msgs = _msgs(30)  # ~15k tokens, over the default soft_limit
        out = compact(msgs, soft_limit=6000, keep_recent=DEFAULT_KEEP_RECENT)
        self.assertLess(len(out), len(msgs))
        # System prompt preserved at the head.
        self.assertEqual(out[0].role, 'system')
        self.assertEqual(out[0].content, 'SYSTEM PROMPT')
        # The most-recent window is kept verbatim.
        self.assertEqual(out[-1].content, msgs[-1].content)

    def test_summary_replaces_middle(self):
        calls = []

        def summarizer(transcript):
            calls.append(transcript)
            return 'EARLY FACTS: the user likes poetry.'

        msgs = _msgs(30)
        out = compact(msgs, soft_limit=6000, keep_recent=4, summarizer=summarizer)
        self.assertEqual(len(calls), 1)  # summarizer called once
        # head + summary + 4 recent
        self.assertEqual(len(out), 1 + 1 + 4)
        self.assertEqual(out[0].content, 'SYSTEM PROMPT')
        self.assertIn('EARLY FACTS', out[1].content)
        self.assertEqual(out[-4:], msgs[-4:])  # recent verbatim

    def test_summarizer_failure_falls_back_to_truncation(self):
        def boom(_transcript):
            raise RuntimeError('summarizer down')

        msgs = _msgs(30)
        out = compact(msgs, soft_limit=6000, keep_recent=4, summarizer=boom)
        # No summary message inserted; just head + recent.
        self.assertEqual(len(out), 1 + 4)
        self.assertEqual(out[0].content, 'SYSTEM PROMPT')
