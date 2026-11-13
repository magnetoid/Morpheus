"""The storefront's settings say only what the code reads.

Five schema keys had no reader and no editor, the Caching page held eight
controls nothing read, and the maintenance switch had no editor at all.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from plugins.models import PluginConfig
from plugins.registry import app_registry

DEAD_KEYS = (
    'enable_guest_checkout',
    'products_per_page',
    'show_out_of_stock',
    'enable_live_search',
    'enable_ai_chat',
)
DEAD_CONTROLS = (
    'serve_webp',
    'responsive_srcset',
    'brotli_enabled',
    'gzip_enabled',
    'min_compress_bytes',
    'inline_critical_css',
    'asset_max_age_seconds',
    'warmup_extra_urls',
)
CACHING = '/dashboard/settings/caching/'


class _Base(TestCase):
    def setUp(self):
        self.plugin = app_registry.get('storefront')
        # The plugin caches its config per process; a test must not leak it.
        self.addCleanup(setattr, self.plugin, '_config_cache', None)
        self.plugin._config_cache = None
        self.staff = Client()
        self.staff.force_login(
            get_user_model().objects.create_user(
                username='sh-staff',
                email='sh@x.test',
                password='pw',
                is_staff=True,
                is_superuser=True,
            )
        )

    def _stored(self):
        self.plugin._config_cache = None
        return dict(PluginConfig.objects.get(plugin_name='storefront').config)


class SchemaTests(_Base):
    def test_dead_keys_are_gone(self):
        props = self.plugin.get_config_schema()['properties']
        for key in DEAD_KEYS:
            self.assertNotIn(key, props)

    def test_removed_controls_are_not_in_the_schema(self):
        props = self.plugin.get_config_schema()['properties']
        for key in DEAD_CONTROLS:
            self.assertNotIn(key, props)

    def test_maintenance_panel(self):
        panel = app_registry.settings_panel('storefront')
        self.assertEqual(panel.category, 'storefront')
        self.assertEqual(
            set(panel.schema['properties']), {'maintenance_mode', 'maintenance_message'}
        )


class MaintenancePanelTests(_Base):
    def test_panel_saves_and_closes_the_shop(self):
        resp = self.staff.post('/dashboard/settings/storefront/', {'maintenance_mode': 'on'})
        self.assertEqual(resp.status_code, 302)
        self.assertIs(self._stored()['maintenance_mode'], True)

        shopper = Client()
        closed = shopper.get('/')
        self.assertEqual(closed.status_code, 503)
        self.assertIn('Back shortly', closed.content.decode())
        # Staff still reach the dashboard and the shop.
        self.assertEqual(self.staff.get('/dashboard/').status_code, 200)
        self.assertEqual(self.staff.get('/').status_code, 200)

    def test_a_regular_post_reopens_the_shop(self):
        # Without JavaScript the card posts a regular form, and an unticked box
        # sends nothing: the form names the boxes it rendered (PR #164 review).
        page = self.staff.get('/dashboard/settings/storefront/').content.decode()
        self.assertIn('name="_booleans" value="maintenance_mode"', page)
        self.staff.post(
            '/dashboard/settings/storefront/',
            {'_booleans': 'maintenance_mode', 'maintenance_mode': 'on'},
        )
        self.assertIs(self._stored()['maintenance_mode'], True)
        self.assertEqual(Client().get('/').status_code, 503)
        resp = self.staff.post(
            '/dashboard/settings/storefront/',
            {'_booleans': 'maintenance_mode', 'maintenance_message': ''},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIs(self._stored()['maintenance_mode'], False)
        self.assertEqual(Client().get('/').status_code, 200)

    def test_a_post_that_names_no_box_leaves_the_switch_alone(self):
        # A page that posts only some keys must not switch off a box it never showed.
        self.staff.post(
            '/dashboard/settings/storefront/',
            {'_booleans': 'maintenance_mode', 'maintenance_mode': 'on'},
        )
        self.staff.post('/dashboard/settings/storefront/', {'maintenance_message': 'Back at noon.'})
        stored = self._stored()
        self.assertIs(stored['maintenance_mode'], True)
        self.assertEqual(stored['maintenance_message'], 'Back at noon.')

    def test_panel_writes_only_its_own_keys(self):
        self.staff.post(
            '/dashboard/settings/storefront/',
            {
                'maintenance_mode': 'on',
                'maintenance_message': 'Back at noon.',
                'lazy_load_images': '',
            },
        )
        stored = self._stored()
        self.assertEqual(stored['maintenance_message'], 'Back at noon.')
        self.assertNotIn('lazy_load_images', stored)

    def test_storefront_page_shows_the_panel_and_general_does_not(self):
        body = self.staff.get('/dashboard/settings/storefront/').content.decode()
        self.assertIn('name="maintenance_mode"', body)
        self.assertIn('name="maintenance_message"', body)
        general = self.staff.get('/dashboard/settings/general/').content.decode()
        self.assertNotIn('name="maintenance_mode"', general)

    def test_palette_anchor_lands_on_a_field_that_exists(self):
        from plugins.installed.admin_dashboard.views_split.palette import _setting_hits

        hits = _setting_hits(['close', 'shop', 'maintenance'], {})
        urls = [h['url'] for h in hits if h['kind'] == 'setting']
        url = next(u for u in urls if u.endswith('maintenance_mode'))
        path, _, anchor = url.partition('#')
        self.assertEqual(path, '/dashboard/settings/storefront/')
        body = self.staff.get(path).content.decode()
        self.assertIn(f'id="{anchor}"', body)

    def test_ajax_panel_save_returns_json(self):
        resp = self.staff.post(
            '/dashboard/settings/storefront/',
            {'maintenance_message': 'Back at noon.'},
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'].split(';')[0], 'application/json')
        self.assertTrue(resp.json()['ok'])
        self.assertIn('maintenance_message', resp.json()['saved'])
        self.assertEqual(self._stored()['maintenance_message'], 'Back at noon.')

    def test_ajax_payments_panel_save_returns_json(self):
        payments = app_registry.get('payments')
        self.addCleanup(setattr, payments, '_config_cache', None)
        resp = self.staff.post(
            '/dashboard/settings/payments/',
            {'high_value_threshold': '750'},
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'].split(';')[0], 'application/json')
        self.assertTrue(resp.json()['ok'])
        self.assertIn('high_value_threshold', resp.json()['saved'])
        payments._config_cache = None
        self.assertEqual(
            PluginConfig.objects.get(plugin_name='payments').config['high_value_threshold'], 750
        )

    def test_message_is_escaped_on_the_closed_page(self):
        self.plugin.set_config('maintenance_mode', True)
        self.plugin.set_config('maintenance_message', '<b>x</b>')
        body = Client().get('/').content.decode()
        self.assertIn('&lt;b&gt;x&lt;/b&gt;', body)
        self.assertNotIn('<b>x</b>', body)


class CachingPageTests(_Base):
    def test_no_dead_controls(self):
        body = self.staff.get(CACHING).content.decode()
        for key in DEAD_CONTROLS:
            self.assertNotIn(f'name="{key}"', body)
        self.assertIn('name="lazy_load_images"', body)
        self.assertIn('name="home_cache_ttl"', body)

    def test_save_keeps_working(self):
        self.staff.post(CACHING, {'action': 'save_assets', 'lazy_load_images': 'on'})
        self.staff.post(
            CACHING,
            {'action': 'save_critical', 'defer_non_critical_js': 'on', 'font_display': 'optional'},
        )
        self.staff.post(
            CACHING, {'action': 'save_warmup', 'post_deploy_warmup': 'on', 'warmup_top_n': '7'}
        )
        stored = self._stored()
        self.assertIs(stored['lazy_load_images'], True)
        self.assertIs(stored['preload_lcp'], False)
        self.assertEqual(stored['font_display'], 'optional')
        self.assertIs(stored['post_deploy_warmup'], True)
        self.assertEqual(stored['warmup_top_n'], 7)
        for key in DEAD_CONTROLS:
            self.assertNotIn(key, stored)

    def test_the_compression_action_is_gone(self):
        self.staff.post(CACHING, {'action': 'save_assets', 'lazy_load_images': 'on'})
        before = self._stored()
        self.staff.post(
            CACHING,
            {'action': 'save_compression', 'brotli_enabled': 'on', 'min_compress_bytes': '9'},
        )
        self.assertEqual(self._stored(), before)


class StaleKeysTests(_Base):
    def test_stale_stored_keys_are_harmless(self):
        PluginConfig.objects.update_or_create(
            plugin_name='storefront',
            defaults={'config': {'enable_ai_chat': False, 'serve_webp': False}},
        )
        self.plugin._config_cache = None
        for url in ('/', CACHING, '/dashboard/settings/storefront/'):
            self.assertEqual(self.staff.get(url).status_code, 200, url)
        body = self.staff.get('/dashboard/settings/storefront/').content.decode()
        self.assertNotIn('enable_ai_chat', body)
