"""Disabling a plugin must silence its hook handlers (ADR 0023).

`deactivate()` intentionally does NOT unwind the hooks a plugin wired in
`ready()` (so a re-enable doesn't double-register them). The safety net is the
hook bus itself: `fire`/`filter` skip any handler owned by a plugin that
app_registry reports as inactive. This is what makes a contributed surface
(product-form card, KPI, activity-feed item) vanish the moment its plugin is
toggled off — the regression behind "I disabled book_product but its Book
details card kept showing".
"""

from __future__ import annotations

from django.test import TestCase

from core.hooks import HookRegistry, MorpheusEvents, hook_registry
from plugins.registry import app_registry

_EVENT = 'test.disable_gating.probe'


class HookOwnerGatingTests(TestCase):
    """The bus honours an injected active-check predicate. Uses a throwaway
    HookRegistry per test; TestCase (not SimpleTestCase) because fire()'s
    remote-webhook dispatch touches the DB (empty here, so a no-op)."""

    def _reg(self):
        reg = HookRegistry()
        return reg

    def test_inactive_owner_skipped_on_fire(self):
        reg = self._reg()
        reg.set_active_check(lambda name: name != 'off_plugin')
        reg.register(_EVENT, lambda **k: 'on', plugin='on_plugin')
        reg.register(_EVENT, lambda **k: 'off', plugin='off_plugin')
        self.assertEqual(reg.fire(_EVENT), ['on'])

    def test_inactive_owner_skipped_on_filter(self):
        reg = self._reg()
        reg.set_active_check(lambda name: name != 'off_plugin')
        reg.register(_EVENT, lambda value, **k: value + ['on'], plugin='on_plugin')
        reg.register(_EVENT, lambda value, **k: value + ['off'], plugin='off_plugin')
        self.assertEqual(reg.filter(_EVENT, value=[]), ['on'])

    def test_core_owned_handler_never_gated(self):
        # plugin=None (a core-owned handler) always runs, even when the active
        # check would reject everything.
        reg = self._reg()
        reg.set_active_check(lambda name: False)
        reg.register(_EVENT, lambda **k: 'core', plugin=None)
        self.assertEqual(reg.fire(_EVENT), ['core'])

    def test_no_active_check_runs_everything(self):
        # Boot default (predicate unset): nothing is gated.
        reg = self._reg()
        reg.register(_EVENT, lambda **k: 'x', plugin='whatever')
        self.assertEqual(reg.fire(_EVENT), ['x'])


class RegistryWiredGatingTests(TestCase):
    """End-to-end: the REAL hook_registry is wired to app_registry.is_active,
    so toggling a plugin off silences its handlers on the shared bus."""

    def setUp(self):
        # A probe handler owned by 'audiobooks' (safe to toggle; see
        # test_disable_guards.HotEnableTests). Clean up whatever we touch.
        self._handler = lambda value, **k: value + ['audiobooks-card']
        hook_registry.register(
            MorpheusEvents.PRODUCT_FORM_CARDS, self._handler, plugin='audiobooks'
        )
        self.addCleanup(hook_registry.unregister, MorpheusEvents.PRODUCT_FORM_CARDS, self._handler)
        self.addCleanup(app_registry.activate, 'audiobooks')

    def test_probe_present_when_active_absent_when_disabled(self):
        app_registry.activate('audiobooks')
        self.assertIn(
            'audiobooks-card',
            hook_registry.filter(MorpheusEvents.PRODUCT_FORM_CARDS, value=[], product=None),
        )
        # Toggle off → the shared bus skips the audiobooks-owned handler.
        app_registry.deactivate('audiobooks')
        self.assertNotIn(
            'audiobooks-card',
            hook_registry.filter(MorpheusEvents.PRODUCT_FORM_CARDS, value=[], product=None),
        )
        # Re-enable → back again (no restart).
        app_registry.activate('audiobooks')
        self.assertIn(
            'audiobooks-card',
            hook_registry.filter(MorpheusEvents.PRODUCT_FORM_CARDS, value=[], product=None),
        )

    def test_active_check_is_registry(self):
        # The predicate the bus uses IS the live registry state.
        self.assertTrue(hook_registry._owner_inactive('no_such_plugin_xyz'))
        self.assertFalse(hook_registry._owner_inactive('admin_dashboard'))
