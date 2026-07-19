"""Regression: a throwaway PluginRegistry must not rebind the global hook
active-check (hunt #12).

Bug (fixed): `PluginRegistry.__init__` unconditionally called
`hook_registry.set_active_check(self.is_active)`. Any throwaway second instance
(e.g. the ones `plugins/tests.py` builds) rebound the shared bus to ITS OWN
empty `_active` set, so `_owner_inactive(<any plugin>)` flipped to True and every
plugin-owned hook handler was silently gated off process-wide. The fix guards
the wiring behind the class attr `PluginRegistry._active_check_wired`, so only
the first (canonical, module-level) registry wires the bus.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from core.hooks import hook_registry
from plugins.registry import PluginRegistry


class RegistryActiveCheckGuardTests(SimpleTestCase):
    def test_wired_flag_set_after_import(self) -> None:
        # The module-level singleton wired the bus at import time.
        self.assertTrue(PluginRegistry._active_check_wired)

    def test_throwaway_instance_does_not_rebind_active_check(self) -> None:
        # 'admin_dashboard' is a protected, always-active plugin in the live
        # singleton, so the shared bus reports its owner as active.
        self.assertFalse(hook_registry._owner_inactive('admin_dashboard'))

        # Capture the exact predicate the bus is using so we can prove identity
        # is preserved (no rebind).
        predicate_before = hook_registry._active_check

        # Build a throwaway registry — its own `_active` set is empty. Under the
        # old bug this rebound the global bus to that empty set.
        throwaway = PluginRegistry()
        self.assertEqual(throwaway._active, set())

        # The global active-check must be UNCHANGED — same predicate object …
        self.assertIs(hook_registry._active_check, predicate_before)
        # … and admin_dashboard must STILL read as active (old bug: flipped True).
        self.assertFalse(hook_registry._owner_inactive('admin_dashboard'))
