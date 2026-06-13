"""Skill bundles + composition into the Worker (`core/agents/skills.py`).

Skills are the canonical specialization mechanism (no per-role agent
subclasses). These lock the dataclass invariants, the registry, and that an
agent's `get_tools()` merges opted-in skill tools with name-dedup.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from core.agents.base import MorpheusAgent
from core.agents.skills import Skill, SkillRegistry
from core.agents.tools import Tool


def _tool(name):
    return Tool(name=name, description='d', handler=lambda **kw: None)


class SkillDataclassTests(SimpleTestCase):
    def test_label_defaults_from_name(self):
        s = Skill(name='catalog_admin', label='')
        self.assertEqual(s.label, 'Catalog Admin')

    def test_list_tools_coerced_to_tuple(self):
        s = Skill(name='x', label='X', tools=[_tool('a')])
        self.assertIsInstance(s.tools, tuple)

    def test_name_required(self):
        with self.assertRaises(ValueError):
            Skill(name='', label='X')


class SkillRegistryTests(SimpleTestCase):
    def test_register_get_resolve(self):
        reg = SkillRegistry()
        s = Skill(name='seo', label='SEO', tools=(_tool('seo.audit'),))
        reg.register(s)
        self.assertIs(reg.get('seo'), s)
        self.assertEqual(reg.resolve(['seo']), [s])

    def test_resolve_skips_unknown(self):
        reg = SkillRegistry()
        reg.register(Skill(name='a', label='A'))
        self.assertEqual([s.name for s in reg.resolve(['a', 'ghost'])], ['a'])

    def test_register_rejects_non_skill(self):
        with self.assertRaises(TypeError):
            SkillRegistry().register(object())


class SkillCompositionTests(SimpleTestCase):
    """get_tools() merges skill tools (uses the real method + global registry)."""

    def setUp(self):
        from core.agents.skills import skill_registry

        self.registry = skill_registry
        self.skill = Skill(name='_test_skill', label='T', tools=(_tool('_test.skill_tool'),))
        self.registry.register(self.skill)

    def tearDown(self):
        self.registry.unregister('_test_skill')

    def _agent(self, *, default_tools=(), uses_skills=()):
        a = MorpheusAgent()
        a.name = 'tester'
        a.label = 'Tester'
        a.scopes = []
        a.default_tools = tuple(default_tools)
        a.uses_skills = tuple(uses_skills)
        return a

    def test_opted_in_skill_tool_appears(self):
        names = {t.name for t in self._agent(uses_skills=['_test_skill']).get_tools()}
        self.assertIn('_test.skill_tool', names)

    def test_default_tool_shadows_skill_tool_of_same_name(self):
        own = _tool('_test.skill_tool')
        tools = self._agent(default_tools=[own], uses_skills=['_test_skill']).get_tools()
        matches = [t for t in tools if t.name == '_test.skill_tool']
        self.assertEqual(len(matches), 1)
        self.assertIs(matches[0], own)  # default wins, no duplicate
