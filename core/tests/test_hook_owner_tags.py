"""An app's hook handler names its owner (v0.197.0).

The bus skips a switched-off app's handlers by the owner each one was registered
with. A handler registered straight on ``hook_registry`` carries none and keeps
running: loyalty_points wired its earn-on-purchase handler that way, so points
were still earned while the app was off. ``Plugin.register_hook`` adds the tag.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from core.hooks import hook_registry
from core.safety import is_plugin_protected

# Registered without an owner today. Each belongs to an app that cannot be
# switched off, so nothing is left running behind a disable. Never add an app
# that can be: register through ``self.register_hook`` instead.
KNOWN_UNTAGGED = {
    ('plugins.installed.agent_core.approvals', 'record_pending'),
    ('plugins.installed.catalog.search.handlers', 'on_product_created'),
    ('plugins.installed.catalog.search.handlers', 'on_product_updated'),
}


def _from_a_test(module: str) -> bool:
    # Other suites register throwaway handlers and leave them on the bus, so in a
    # whole-suite run they are still there when this test reads it.
    parts = module.split('.')
    return 'tests' in parts or parts[-1].startswith(('test_', 'tests_'))


def _untagged() -> set[tuple[str, str]]:
    found = set()
    for entries in hook_registry._handlers.values():
        for entry in entries:
            _priority, handler, _mode, owner = hook_registry._unpack(entry)
            module = getattr(handler, '__module__', '') or ''
            if owner is not None or not module.startswith('plugins.installed.'):
                continue
            if not _from_a_test(module):
                found.add((module, getattr(handler, '__qualname__', repr(handler))))
    return found


class HookOwnerTagTests(SimpleTestCase):
    def test_every_app_handler_names_its_owner(self):
        self.assertEqual(_untagged() - KNOWN_UNTAGGED, set())

    def test_a_handler_a_test_left_behind_is_not_an_apps(self):
        def leftover(**_kwargs):
            return None

        leftover.__module__ = 'plugins.installed.payments.tests.test_paypal'
        hook_registry.register('test.owner_tags.leftover', leftover)
        self.addCleanup(hook_registry._handlers.pop, 'test.owner_tags.leftover', None)
        self.assertEqual(_untagged() - KNOWN_UNTAGGED, set())
        self.assertFalse(_from_a_test('plugins.installed.testimonials.handlers'))

    def test_the_known_untagged_handlers_belong_to_protected_apps(self):
        for module, _name in KNOWN_UNTAGGED:
            app = module.split('.')[2]
            self.assertTrue(is_plugin_protected(app), app)

    def test_loyalty_stops_earning_with_the_app(self):
        from morpheus.core import MorpheusEvents

        owners = [
            hook_registry._unpack(entry)[3]
            for entry in hook_registry._handlers.get(MorpheusEvents.ORDER_PAID, [])
            if hook_registry._unpack(entry)[1].__qualname__ == '_on_order_paid'
            and hook_registry._unpack(entry)[1].__module__.endswith('loyalty_points.services')
        ]
        self.assertEqual(owners, ['loyalty_points'])
