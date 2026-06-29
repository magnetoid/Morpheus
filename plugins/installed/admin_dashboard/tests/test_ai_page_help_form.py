from django.test import TestCase

from core.models import StoreSettings
from plugins.installed.admin_dashboard.forms.settings import StoreGeneralForm


class AiPageHelpFormTests(TestCase):
    def test_form_saves_ai_page_help(self):
        s = StoreSettings.objects.create(store_name='T')
        form = StoreGeneralForm(
            data={
                'store_name': 'T',
                'primary_currency': 'USD',
                'country': 'US',
                'timezone': 'UTC',
                'ai_page_help': 'on',
            },
            instance=s,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        s.refresh_from_db()
        self.assertTrue(s.ai_page_help)

    def test_templatetag_default_off(self):
        from plugins.installed.admin_dashboard.templatetags.morph_dashboard import (
            get_ai_page_help,
        )

        self.assertFalse(get_ai_page_help())
