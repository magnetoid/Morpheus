from django.test import SimpleTestCase

from plugins.installed.admin_dashboard.templatetags.morph_dashboard import get_ai_page_help


class AiPageHelpDefaultTests(SimpleTestCase):
    def test_templatetag_default_off(self):
        self.assertFalse(get_ai_page_help())
