"""Core-language picker (Settings → General) persists to StoreSettings.
Foundation for URL-prefixed localization (Phase 1a)."""

from django.test import TestCase

from core.models import StoreSettings
from plugins.installed.admin_dashboard.forms.settings import StoreGeneralForm


class CoreLanguageSettingTests(TestCase):
    def test_default_is_english(self):
        s = StoreSettings.objects.create(store_name='Shop')
        self.assertEqual(s.core_language, 'en')

    def test_form_saves_core_language(self):
        form = StoreGeneralForm(
            data={
                'store_name': 'Shop',
                'primary_currency': 'USD',
                'country': 'US',
                'core_language': 'fr',
                'timezone': 'UTC',
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save()
        self.assertEqual(instance.core_language, 'fr')
        self.assertEqual(StoreSettings.objects.first().core_language, 'fr')

    def test_core_language_rejects_unknown_code(self):
        form = StoreGeneralForm(
            data={
                'store_name': 'Shop',
                'primary_currency': 'USD',
                'country': 'US',
                'core_language': 'xx-not-a-lang',
                'timezone': 'UTC',
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('core_language', form.errors)
