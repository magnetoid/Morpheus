"""The language bar: a block that is the same for every visitor, decided in the browser."""

from __future__ import annotations

import json
import re
from pathlib import Path

from django.template import engines
from django.template.loader import get_template
from django.test import TestCase, override_settings

from plugins.registry import app_registry

BILINGUAL = {'LANGUAGES': [('en', 'English'), ('sr', 'Srpski')], 'LANGUAGE_CODE': 'en'}
SINGLE = {'LANGUAGES': [('en', 'English')], 'LANGUAGE_CODE': 'en'}
APP = Path(__file__).resolve().parent.parent


def _render():
    tpl = engines['django'].from_string("{% include 'localization/blocks/language_bar.html' %}")
    return tpl.render({'csp_nonce': 'N0NCE'})


class LanguageBarTests(TestCase):
    def setUp(self):
        self.plugin = app_registry.get('localization')
        self.plugin._config_cache = {}
        self.addCleanup(setattr, self.plugin, '_config_cache', None)

    def _on(self, value=True):
        self.plugin._config_cache = {'suggest_language': value}

    def test_off_by_default_renders_nothing(self):
        with override_settings(**BILINGUAL):
            self.assertEqual(_render().strip(), '')

    def test_off_when_setting_false(self):
        self._on(False)
        with override_settings(**BILINGUAL):
            self.assertEqual(_render().strip(), '')

    def test_single_language_store_renders_nothing(self):
        self._on()
        with override_settings(**SINGLE):
            self.assertEqual(_render().strip(), '')

    def test_bilingual_store_renders_data_script_and_css(self):
        self._on()
        with override_settings(**BILINGUAL):
            html = _render()
        self.assertNotIn('<link', html)  # the script adds the stylesheet when it shows the bar
        self.assertRegex(html, r'<script nonce="N0NCE" src="[^"]*language-bar[^"]*\.js" defer>')
        raw = re.search(
            r'<script id="morpheus-language-bar" type="application/json">(.*?)</script>', html, re.S
        )
        payload = json.loads(raw.group(1))
        self.assertIn('localization/language-bar', payload['css'])
        data = payload['languages']
        self.assertEqual(set(data), {'en', 'sr'})
        self.assertEqual(data['en']['also_in'], 'This page is also in {name}.')
        self.assertEqual(data['en']['switch'], 'Switch')
        self.assertEqual(data['sr']['name'], 'Srpski')
        self.assertEqual(data['sr']['switch'], 'Prebaci')
        self.assertEqual(data['sr']['stay'], 'Ostani')
        self.assertIn('{name}', data['sr']['also_in'])
        self.assertNotIn('on' + 'click=', html)

    def test_files_and_template_exist(self):
        self.assertTrue((APP / 'static/localization/language-bar.js').is_file())
        self.assertTrue((APP / 'static/localization/language-bar.css').is_file())
        get_template('localization/blocks/language_bar.html')

    def test_block_contributed_to_global_head(self):
        slots = {(b.slot, b.template) for b in self.plugin.contribute_storefront_blocks()}
        self.assertIn(('global_head', 'localization/blocks/language_bar.html'), slots)

    def test_setting_is_in_the_schema_default_off(self):
        prop = self.plugin.get_config_schema()['properties']['suggest_language']
        self.assertIs(prop['default'], False)


class LanguageBarSwitchTests(TestCase):
    """The switch lives on the Translations page, beside the languages it offers."""

    PAGE = '/dashboard/apps/localization/translations/'

    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse

        self.plugin = app_registry.get('localization')
        self.addCleanup(self.plugin.invalidate_config_cache)
        self.url = reverse('localization:language_bar')
        self.user = get_user_model().objects.create_superuser('s', 's@x.test', 'pw')

    def _value(self):
        self.plugin.invalidate_config_cache()
        return self.plugin.get_config_value('suggest_language', False)

    def test_no_separate_settings_panel(self):
        self.assertIsNone(self.plugin.contribute_settings_panel())

    @override_settings(**BILINGUAL)
    def test_the_page_turns_the_bar_on_and_off(self):
        self.client.force_login(self.user)
        page = self.client.get(self.PAGE).content.decode()
        self.assertIn('name="suggest_language"', page)
        self.client.post(self.url, {'suggest_language': 'on'})
        self.assertTrue(self._value())
        self.assertIn('checked', self.client.get(self.PAGE).content.decode())
        self.client.post(self.url, {})
        self.assertFalse(self._value())

    @override_settings(**SINGLE)
    def test_a_one_language_store_shows_no_switch(self):
        self.client.force_login(self.user)
        self.assertNotIn('name="suggest_language"', self.client.get(self.PAGE).content.decode())

    def test_anonymous_cannot_switch_it(self):
        r = self.client.post(self.url, {'suggest_language': 'on'})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(self._value())
