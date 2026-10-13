"""Janus keeps its own skills; the old in-process learned-skills loop is gone.

Old Linda distilled "learned skills" (LearnedSkill rows, the skills.distill /
skills.list / skills.record_outcome tools) and a post-run reflection counted their
outcomes. Janus has its own skills toolset (skills_list / skill_view / skill_manage,
core/assistant/janus_skills), so the second system only duplicated it. No store had
a single row when it was removed (v0.104.0).
"""

from __future__ import annotations

import importlib

from django.test import SimpleTestCase


class OldSkillsGoneTests(SimpleTestCase):
    def test_no_old_skill_tools_in_the_catalogue(self):
        from core.assistant.tools import get_default_tools

        names = {t.name for t in get_default_tools()}
        self.assertFalse({'skills.distill', 'skills.list', 'skills.record_outcome'} & names)

    def test_the_old_skill_and_reflection_modules_are_gone(self):
        for module in ('core.assistant.tools.skills', 'core.assistant.reflection'):
            with self.assertRaises(ModuleNotFoundError, msg=module):
                importlib.import_module(module)

    def test_the_model_is_gone(self):
        from core.assistant import models

        self.assertFalse(hasattr(models, 'LearnedSkill'))

    def test_janus_still_has_its_own_skills(self):
        from core.assistant.janus_contract import TOOLSETS

        self.assertEqual(TOOLSETS['skills'], {'skills_list', 'skill_view', 'skill_manage'})
