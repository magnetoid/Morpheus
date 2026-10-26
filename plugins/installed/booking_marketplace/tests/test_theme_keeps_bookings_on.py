"""The montenegro theme links this app's pages from its header, footer, 404 and search
pages, so while it is the active theme the app cannot be switched off (v0.124.0).
Switching it off used to make every page answer 500."""

from __future__ import annotations

from django.test import TestCase

from core.safety import protection_reason
from themes.registry import theme_registry


class MontenegroKeepsBookingsOnTests(TestCase):
    def test_bookings_cannot_be_switched_off_under_montenegro(self):
        self.addCleanup(setattr, theme_registry, '_active_name', theme_registry._active_name)
        theme_registry.set_active('montenegro')
        self.assertIn('Montenegro', protection_reason('booking_marketplace'))

    def test_another_theme_leaves_the_switch_alone(self):
        self.addCleanup(setattr, theme_registry, '_active_name', theme_registry._active_name)
        theme_registry.set_active('dot_books')
        self.assertEqual(protection_reason('booking_marketplace'), '')
