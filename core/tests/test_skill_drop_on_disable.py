"""Regression: a plugin's contributed agent skills are unregistered on disable
(hunt #14).

Bug (fixed): `_collect_contributions` registered a plugin's `contribute_skills()`
into the process-wide `skill_registry`, but `_drop_contributions` never removed
them — so a disabled plugin's skill (and the tools it re-injects into a Worker)
stayed resolvable, leaking a capability the merchant turned off. The fix records
each contributed skill name in `self._plugin_skills[plugin]` and unregisters them
in `_drop_contributions` via `skill_registry.unregister(name)`.

This drives the real singleton `plugin_registry` toggle and restores state on
cleanup so it can't pollute sibling tests.
"""

from __future__ import annotations

from django.test import TestCase

from core.agents.skills import skill_registry
from plugins.registry import plugin_registry

# Plugins that contribute a same-named skill (verified: inventory/crm/seo each
# return a Skill whose name == the plugin name).
_CANDIDATES = ('seo', 'inventory', 'crm')


class SkillDropOnDisableTests(TestCase):
    def _pick_active_skill_plugin(self) -> str:
        for name in _CANDIDATES:
            if plugin_registry.is_active(name) and skill_registry.get(name) is not None:
                return name
        self.skipTest('no active skill-contributing candidate plugin found')

    def test_skill_unregistered_on_deactivate(self) -> None:
        name = self._pick_active_skill_plugin()

        # Restore the plugin (and thus its skill) no matter how this test exits,
        # so the shared registry is left exactly as we found it.
        self.addCleanup(plugin_registry.activate, name)

        # Precondition: the skill resolves while the plugin is active.
        self.assertIsNotNone(skill_registry.get(name))

        # Disable → the contributed skill must be unregistered.
        plugin_registry.deactivate(name)
        self.assertIsNone(
            skill_registry.get(name),
            f'skill {name!r} still resolvable after its plugin was disabled',
        )

        # Re-enable → the skill comes back (also what addCleanup relies on).
        plugin_registry.activate(name)
        self.assertIsNotNone(skill_registry.get(name))
