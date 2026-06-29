from django.test import TestCase
from core.models import StoreSettings


class AiPageHelpSettingTests(TestCase):
    def test_default_is_off(self):
        StoreSettings.objects.create(store_name='Test')
        self.assertFalse(StoreSettings.get('ai_page_help', False))

    def test_can_enable(self):
        StoreSettings.objects.create(store_name='Test', ai_page_help=True)
        self.assertTrue(StoreSettings.get('ai_page_help', False))

    def test_guided_ux_mode_removed(self):
        self.assertFalse(any(f.name == 'guided_ux_mode' for f in StoreSettings._meta.get_fields()))
