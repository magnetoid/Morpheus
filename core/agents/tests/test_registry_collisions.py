"""Tool-name collision detection in the agent registry.

Two plugins registering the same tool name is a one-concept-many-owners bug:
the winner is decided by plugin load order, so the MCP-served version becomes
non-deterministic (and, for cart.add_item, the loser couldn't even run under the
MCP cart cluster). register_tool now surfaces cross-plugin clashes via
`collisions()` (and a warning) instead of a silent debug-level overwrite.
"""

from __future__ import annotations

from django.test import SimpleTestCase, TestCase

from core.agents.registry import AgentRegistry, agent_registry
from core.agents.tools import Tool


def _tool(name: str) -> Tool:
    return Tool(name=name, description='x', handler=lambda **kw: None)


class RegisterToolCollisionTests(SimpleTestCase):
    def test_cross_plugin_collision_is_refused_and_recorded(self):
        from django.core.exceptions import ImproperlyConfigured

        r = AgentRegistry()
        r.register_tool(_tool('x.do'), plugin='alpha')
        # FIRST OWNER WINS (v0.55.0): the second plugin is refused, and under
        # tests the refusal RAISES so a duplicate can never ship silently
        # (last-writer-wins once served an ungated inventory.adjust_stock).
        with self.assertRaises(ImproperlyConfigured):
            r.register_tool(_tool('x.do'), plugin='beta')
        self.assertEqual(r.collisions(), [('x.do', 'alpha', 'beta')])
        self.assertEqual(r.get_tool('x.do').plugin, 'alpha')

    def test_deliberate_replace_is_allowed(self):
        # A test that swaps a tool passes replace=True (and restores after).
        r = AgentRegistry()
        r.register_tool(_tool('x.do'), plugin='alpha')
        r.register_tool(_tool('x.do'), plugin='beta', replace=True)
        self.assertEqual(r.get_tool('x.do').plugin, 'beta')

    def test_same_plugin_reregister_is_not_a_collision(self):
        # Reactivation re-registers a plugin's own tools — benign, not a clash.
        r = AgentRegistry()
        r.register_tool(_tool('x.do'), plugin='alpha')
        r.register_tool(_tool('x.do'), plugin='alpha')
        self.assertEqual(r.collisions(), [])

    def test_no_owner_replacement_is_not_a_collision(self):
        r = AgentRegistry()
        r.register_tool(_tool('x.do'))  # no plugin owner
        r.register_tool(_tool('x.do'), plugin='alpha')
        self.assertEqual(r.collisions(), [])


class LiveRegistryCollisionBaselineTests(TestCase):
    """CI guard: ZERO collisions in the actually-loaded plugin set.

    The old baseline tolerated three duplicate families (agent_core's parallel
    analytics/inventory tools) — one of which silently served an ungated
    `inventory.adjust_stock` in place of the approval-gated original. All
    consolidated in v0.55.0; the baseline is empty and must stay empty
    (register_tool now refuses cross-plugin overwrites and raises under
    DEBUG/tests, so a new duplicate fails at registration, not here).
    """

    _KNOWN: set[str] = set()

    def test_no_new_tool_name_collisions(self):
        names = {c[0] for c in agent_registry.collisions()}
        new = names - self._KNOWN
        self.assertEqual(new, set(), f'NEW tool-name collision(s): {sorted(new)}')

    def test_cart_add_item_collision_is_resolved(self):
        names = {c[0] for c in agent_registry.collisions()}
        self.assertNotIn('cart.add_item', names)
