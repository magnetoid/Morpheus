"""Phase 0 (Hermes provider) + Phase 1 (self-authored skills) of the Linda
self-learning uplift. See docs/plans/linda-self-learning-uplift-2026-06.md."""

from __future__ import annotations

from django.test import SimpleTestCase, TestCase

from core.agents.llm import _PROVIDER_CLASSES, HermesProvider, OpenAIProvider
from core.agents.skills import skill_registry
from core.agents.tools import ToolError
from core.assistant.models import LearnedSkill
from core.assistant.tools.skills import (
    all_resolvable_tools,
    load_learned_skills,
    skills_distill_tool,
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
