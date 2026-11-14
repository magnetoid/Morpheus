"""The Google Ads conversion fields live on the Tracking page, once."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.registry import app_registry

_PAGE = '/dashboard/tracking/settings/'
_ID = 'google_ads_conversion_id'
_LABEL = 'google_ads_purchase_label'


class AdsFieldsOnTrackingPageTests(TestCase):
    def setUp(self):
        self.plugin = app_registry.get('tracking')
        for key in (_ID, _LABEL):
            self.addCleanup(self.plugin.set_config, key, '')
        self.staff = get_user_model().objects.create_user(
            username='ads-staff', email='ads@example.test', password='x', is_staff=True
        )
        self.staff.is_superuser = True
        self.staff.save()

    def test_there_is_no_separate_settings_panel(self):
        self.assertIsNone(app_registry.settings_panel('tracking'))

    def test_the_page_shows_both_fields_with_the_stored_values(self):
        self.plugin.set_config(_ID, 'AW-555')
        self.plugin.set_config(_LABEL, 'lbl-9')
        self.client.force_login(self.staff)
        html = self.client.get(_PAGE).content.decode()
        self.assertIn(f'name="{_ID}"', html)
        self.assertIn(f'name="{_LABEL}"', html)
        self.assertIn('value="AW-555"', html)
        self.assertIn('value="lbl-9"', html)

    def test_a_staff_post_saves_both_stripped_and_blank_stays_blank(self):
        self.client.force_login(self.staff)
        self.client.post(_PAGE, {'action': 'ads', _ID: '  AW-123456  ', _LABEL: ' abcXYZ '})
        self.assertEqual(self.plugin.get_config_value(_ID, ''), 'AW-123456')
        self.assertEqual(self.plugin.get_config_value(_LABEL, ''), 'abcXYZ')
        self.client.post(_PAGE, {'action': 'ads', _ID: '   ', _LABEL: ''})
        self.assertEqual(self.plugin.get_config_value(_ID, 'x'), '')
        self.assertEqual(self.plugin.get_config_value(_LABEL, 'x'), '')

    def test_an_anonymous_post_saves_nothing(self):
        self.client.post(_PAGE, {'action': 'ads', _ID: 'AW-1', _LABEL: 'l'})
        self.assertEqual(self.plugin.get_config_value(_ID, ''), '')
        self.assertEqual(self.plugin.get_config_value(_LABEL, ''), '')
