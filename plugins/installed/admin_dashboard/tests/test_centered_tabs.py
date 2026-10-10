"""Linda's tab strip is centred, like her chat (owner's ask, 2026-10-10).

Centring is a property of the section (``NavSection.centered``), so every tab
of the Linda section keeps the strip in the same place, and other sections are
untouched.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.admin_dashboard import navigation


class CenteredTabsTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='tabs-owner',
            email='tabs-owner@example.test',
            password='x',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(user)

    def test_only_the_linda_section_is_centred(self):
        centred = {s.key for s in navigation.SECTIONS if s.centered}
        self.assertEqual(centred, {'ai'})

    def test_lindas_tabs_render_centred(self):
        html = self.client.get('/dashboard/assistant/').content.decode()
        self.assertIn('class="hub-tabs hub-tabs--centered"', html)

    def test_other_sections_keep_their_tabs_where_they_were(self):
        html = self.client.get('/dashboard/orders/').content.decode()
        self.assertIn('<nav class="hub-tabs"', html)
        self.assertNotIn('class="hub-tabs hub-tabs--centered"', html)
