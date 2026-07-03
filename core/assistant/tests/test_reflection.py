"""Release 1 of docs/plans/linda-self-learning-2026-07.md.

1a — query-aware memory injection (single injection point, semantic ranking).
1b — post-run reflection: lessons → LindaMemory, verdicts → LearnedSkill
     counters (via record_skill_outcome), tool gaps → `tool_gap.*` rows.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from django.test import TestCase

from core.agents.llm import LLMResponse, MockLLMProvider
from core.assistant.models import LearnedSkill, LindaMemory
from core.assistant.prompts import build_system_prompt
from core.assistant.reflection import reflect_on_worker_run
from core.assistant.tools.memory import get_recent_memories, memory_remember_tool


class _FakeRun:
    """Duck-typed AgentRun — reflection only touches these attributes."""

    def __init__(self, *, skills=(), state='completed', final_text='done', error=''):
        self.id = 'test-run'
        self.user_message = 'audit the catalog'
        self.state = state
        self.final_text = final_text
        self.error = error
        self.metadata = {'skills': list(skills)}


def _reflection_provider(payload: dict) -> MockLLMProvider:
    return MockLLMProvider(responses=[LLMResponse(text=json.dumps(payload))], echo_user=False)


def _ship_concept_embed(text: str):
    t = (text or '').lower()
    hit = any(w in t for w in ('warehouse', 'berlin', 'ship', 'parcel', 'fulfil'))
    return [1.0, 0.0] if hit else [0.0, 1.0]


class QueryAwareInjectionTests(TestCase):
    def test_system_prompt_no_longer_injects_memories(self):
        memory_remember_tool.handler(key='postmark', value='prefers Postmark for email')
        self.assertNotIn('[MEMORY]', build_system_prompt())

    @patch('core.embeddings.embed', side_effect=_ship_concept_embed)
    def test_query_lifts_semantic_match_over_recent_noise(self, _mock):
        memory_remember_tool.handler(key='fulfilment', value='our warehouse is in Berlin')
        # 30 newer unrelated rows — under recency-only ranking with limit=20
        # the fulfilment fact would be pushed out entirely.
        for i in range(30):
            memory_remember_tool.handler(key=f'noise_{i}', value=f'unrelated fact {i}')

        recency_only = get_recent_memories(limit=20)
        self.assertNotIn('fulfilment', {r['key'] for r in recency_only})

        with_query = get_recent_memories(limit=20, query='where do my parcels leave from')
        self.assertEqual(with_query[0]['key'], 'fulfilment')

    def test_query_embedding_failure_falls_back_to_decay(self):
        memory_remember_tool.handler(key='postmark', value='prefers Postmark')
        with patch('core.embeddings.embed', side_effect=RuntimeError('provider down')):
            rows = get_recent_memories(limit=20, query='email provider')
        self.assertIn('postmark', {r['key'] for r in rows})


class ReflectionTests(TestCase):
    def _skill(self, name='seo-audit', **kw) -> LearnedSkill:
        defaults = {'label': name, 'tool_names': []}
        defaults.update(kw)
        return LearnedSkill.objects.create(name=name, **defaults)

    def test_success_updates_counters_and_stores_lessons(self):
        self._skill()
        provider = _reflection_provider(
            {
                'outcome': 'success',
                'lessons': [
                    {
                        'key': 'meta_descriptions_thin',
                        'value': 'Product meta descriptions are mostly under 50 chars.',
                    }
                ],
                'tool_gaps': [],
            }
        )
        summary = reflect_on_worker_run(_FakeRun(skills=['seo-audit']), provider=provider)

        self.assertEqual(summary['outcome'], 'success')
        row = LearnedSkill.objects.get(name='seo-audit')
        self.assertEqual((row.uses, row.successes, row.failures), (1, 1, 0))
        lesson = LindaMemory.objects.get(key='meta_descriptions_thin')
        self.assertEqual(lesson.source, 'inferred')
        self.assertTrue(lesson.embedding)

    def test_failure_can_auto_disable_a_bad_skill(self):
        # 4 prior uses, 0 successes — this failure crosses the retire threshold.
        self._skill(uses=4, successes=0, failures=4)
        provider = _reflection_provider({'outcome': 'failure', 'lessons': [], 'tool_gaps': []})
        summary = reflect_on_worker_run(
            _FakeRun(skills=['seo-audit'], state='failed'), provider=provider
        )

        self.assertEqual(summary['skills_disabled'], ['seo-audit'])
        self.assertFalse(LearnedSkill.objects.get(name='seo-audit').enabled)
        note = LindaMemory.objects.get(key='skill_disabled.seo_audit')
        self.assertIn('auto-disabled', note.value)

    def test_unclear_outcome_records_nothing_on_skills(self):
        self._skill()
        provider = _reflection_provider({'outcome': 'unclear', 'lessons': [], 'tool_gaps': []})
        reflect_on_worker_run(_FakeRun(skills=['seo-audit']), provider=provider)
        self.assertEqual(LearnedSkill.objects.get(name='seo-audit').uses, 0)

    def test_tool_gap_counter_increments_on_repeat(self):
        payload = {'outcome': 'success', 'lessons': [], 'tool_gaps': ['bulk price editor']}
        reflect_on_worker_run(_FakeRun(), provider=_reflection_provider(payload))
        reflect_on_worker_run(_FakeRun(), provider=_reflection_provider(payload))
        row = LindaMemory.objects.get(key='tool_gap.bulk_price_editor')
        self.assertTrue(row.value.startswith('seen=2'))

    def test_lessons_capped_at_two(self):
        provider = _reflection_provider(
            {
                'outcome': 'success',
                'lessons': [{'key': f'k{i}', 'value': f'lesson {i}'} for i in range(5)],
                'tool_gaps': [],
            }
        )
        summary = reflect_on_worker_run(_FakeRun(), provider=provider)
        self.assertEqual(summary['lessons'], 2)

    def test_unparseable_reflection_is_skipped(self):
        provider = MockLLMProvider(responses=[LLMResponse(text='not json at all')], echo_user=False)
        summary = reflect_on_worker_run(_FakeRun(), provider=provider)
        self.assertIn('skipped', summary)

    def test_provider_error_never_raises(self):
        class _Boom:
            name = 'boom'

            def respond(self, **kw):
                raise RuntimeError('provider exploded')

        summary = reflect_on_worker_run(_FakeRun(), provider=_Boom())
        self.assertIn('skipped', summary)

    def test_unconfigured_provider_skips_without_llm_call(self):
        summary = reflect_on_worker_run(_FakeRun(), provider=None)
        # Test env has no keys → get_default_provider resolves to mock/unconfigured.
        self.assertEqual(summary, {'skipped': 'no provider configured'})
