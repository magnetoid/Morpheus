"""A regular post can untick a box on an app's own settings page (PR #164 review).

That page posts without JavaScript, and an unticked checkbox sends nothing, so
the form names each box it renders in `_booleans` and the save turns a named,
absent box off. Before, no regular post could switch a box off: a merchant could
close the shop from the maintenance card and not reopen it.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.models import PluginConfig
from plugins.registry import app_registry


class RegularPostUnticksABoxTests(TestCase):
    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user(
                username='box-staff', email='box@x.test', is_staff=True, is_superuser=True
            )
        )

    def _page_with_a_box(self):
        for entry in app_registry.all_settings_panels():
            props = entry['panel'].schema.get('properties') or {}
            box = next((k for k, v in props.items() if v.get('type') == 'boolean'), None)
            if box is None:
                continue
            url = f'/dashboard/settings/{entry["plugin"]}/'
            resp = self.client.get(url)
            used = [t.name for t in resp.templates]
            if resp.status_code == 200 and 'admin_dashboard/plugin_settings.html' in used:
                return entry['plugin'], box, url, resp.content.decode()
        self.fail('no app settings page renders a checkbox')

    def _stored(self, name, key):
        return PluginConfig.objects.get(plugin_name=name).config[key]

    def test_a_named_box_left_unticked_is_saved_as_off(self):
        name, box, url, body = self._page_with_a_box()
        self.addCleanup(app_registry.get(name).invalidate_config_cache)
        self.assertIn(f'name="_booleans" value="{box}"', body)
        self.client.post(url, {'_booleans': box, box: 'on'})
        self.assertIs(self._stored(name, box), True)
        self.client.post(url, {'_booleans': box})
        self.assertIs(self._stored(name, box), False)

    def test_a_post_that_names_no_box_keeps_it(self):
        name, box, url, _ = self._page_with_a_box()
        self.addCleanup(app_registry.get(name).invalidate_config_cache)
        self.client.post(url, {'_booleans': box, box: 'on'})
        self.client.post(url, {})
        self.assertIs(self._stored(name, box), True)
