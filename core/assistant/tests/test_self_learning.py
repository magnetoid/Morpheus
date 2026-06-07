"""Phase 0 (Hermes provider) + Phase 1 (self-authored skills) of the Linda
self-learning uplift. See docs/plans/linda-self-learning-uplift-2026-06.md."""

from __future__ import annotations

from django.test import SimpleTestCase, TestCase

from core.agents.llm import _PROVIDER_CLASSES, HermesProvider, OpenAIProvider
from core.agents.skills import Skill, skill_registry
from core.agents.tools import ToolError
from core.assistant.models import LearnedSkill
from core.assistant.tools.skills import (
    all_resolvable_tools,
    load_learned_skills,
    record_skill_outcome,
    skills_distill_tool,
    skills_list_tool,
    skills_record_outcome_tool,
)
from plugins.installed.ai_assistant.services.config import get_provider_config


class HermesProviderTests(SimpleTestCase):
    def test_hermes_registered_as_provider(self):
        self.assertIs(_PROVIDER_CLASSES.get('hermes'), HermesProvider)
        self.assertTrue(issubclass(HermesProvider, OpenAIProvider))  # OpenAI-compatible

    def test_hermes_config_defaults_resolve(self):
        cfg = get_provider_config('hermes')
        self.assertIn('openrouter.ai', cfg.base_url)
        self.assertIn('hermes', cfg.model)


class SkillDistillTests(TestCase):
    def _a_real_tool_name(self) -> str:
        return next(iter(all_resolvable_tools()))

    def test_distill_creates_and_registers_skill(self):
        tname = self._a_real_tool_name()
        res = skills_distill_tool.invoke(
            {
                'name': 'Restock Low Inventory',
                'label': 'Restock low inventory',
                'description': 'Find low-stock products and reorder.',
                'system_prompt_prelude': 'Check stock, then reorder the low ones.',
                'tool_names': [tname],
            }
        )
        self.assertTrue(res.output['created'])
        self.assertEqual(res.output['name'], 'restock-low-inventory')  # slugified
        # Persisted...
        row = LearnedSkill.objects.get(name='restock-low-inventory')
        self.assertEqual(row.tool_names, [tname])
        self.assertTrue(row.enabled)
        # ...and registered at runtime, resolving the tool object.
        skill = skill_registry.get('restock-low-inventory')
        self.assertIsNotNone(skill)
        self.assertEqual(len(skill.tools), 1)

    def test_distill_rejects_unknown_tool(self):
        with self.assertRaises(ToolError):
            skills_distill_tool.invoke(
                {'name': 'bad', 'label': 'Bad', 'tool_names': ['definitely.not.a.tool']}
            )

    def test_distill_requires_at_least_one_tool(self):
        with self.assertRaises(ToolError):
            skills_distill_tool.invoke({'name': 'empty', 'label': 'Empty', 'tool_names': []})

    def test_distill_updates_and_bumps_version(self):
        tname = self._a_real_tool_name()
        skills_distill_tool.invoke({'name': 'dup', 'label': 'Dup', 'tool_names': [tname]})
        res2 = skills_distill_tool.invoke({'name': 'dup', 'label': 'Dup v2', 'tool_names': [tname]})
        self.assertFalse(res2.output['created'])
        self.assertEqual(res2.output['version'], 2)

    def test_load_learned_skills_registers_enabled_only(self):
        tname = self._a_real_tool_name()
        LearnedSkill.objects.create(name='on', label='On', tool_names=[tname], enabled=True)
        LearnedSkill.objects.create(name='off', label='Off', tool_names=[tname], enabled=False)
        loaded = load_learned_skills()
        self.assertGreaterEqual(loaded, 1)
        self.assertIsNotNone(skill_registry.get('on'))
        self.assertIsNone(skill_registry.get('off'))


class SkillOutcomeTests(TestCase):
    def _skill(self, name='s', **kw):
        kw.setdefault('enabled', True)
        return LearnedSkill.objects.create(name=name, label=name, tool_names=['x'], **kw)

    def test_record_outcome_counts(self):
        self._skill()
        record_skill_outcome('s', True)
        record_skill_outcome('s', False)
        s = LearnedSkill.objects.get(name='s')
        self.assertEqual(s.uses, 2)
        self.assertEqual(s.successes, 1)
        self.assertEqual(s.failures, 1)
        self.assertEqual(s.success_rate(), 0.5)

    def test_auto_prune_on_repeated_failure(self):
        s = self._skill(name='flaky')
        skill_registry.register(Skill(name='flaky', label='Flaky'))
        # 5 failures → below threshold after MIN_USES → auto-retired.
        for _ in range(5):
            record_skill_outcome('flaky', False)
        s.refresh_from_db()
        self.assertFalse(s.enabled)
        self.assertIsNone(skill_registry.get('flaky'))

    def test_good_skill_not_pruned(self):
        s = self._skill(name='solid')
        for _ in range(6):
            record_skill_outcome('solid', True)
        s.refresh_from_db()
        self.assertTrue(s.enabled)

    def test_record_outcome_tool_unknown(self):
        with self.assertRaises(ToolError):
            skills_record_outcome_tool.invoke({'name': 'nope', 'success': True})

    def test_skills_list_tool(self):
        self._skill(name='visible')
        self._skill(name='hidden', enabled=False)
        out = skills_list_tool.invoke({}).output
        names = [s['name'] for s in out['skills']]
        self.assertIn('visible', names)
        self.assertNotIn('hidden', names)
