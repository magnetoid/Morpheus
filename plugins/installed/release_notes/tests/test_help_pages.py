"""The Help area's pages: /dashboard/help/ and /dashboard/help/<app>/."""

from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.registry import app_registry

_OFF_SAMPLE = (
    'reviews',
    'newsletter',
    'feedback',
    'gift_cards',
    'webstories',
    'crm',
    'dynamics',
    'tax',
)


def _set_roles(mode: str) -> None:
    plugin = app_registry.get('rbac')
    plugin.set_config('enforcement_mode', mode)
    plugin.invalidate_config_cache()


class HelpPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            username='help-staff', email='help@example.test', password='pw', is_staff=True
        )

    def setUp(self):
        self.client.force_login(self.staff)

    def _get(self, url: str) -> str:
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, url)
        return resp.content.decode()

    def _section(self, html: str, marker: str) -> str:
        start = html.index(marker)
        return html[start : html.index('</section>', start)]

    def test_the_index_lists_the_apps_that_are_on_by_area(self):
        html = self._get('/dashboard/help/')
        self.assertIn(
            'href="/dashboard/help/reviews/"', self._section(html, 'data-help-area="Products"')
        )
        self.assertNotIn('data-help-off', html)

    def test_an_app_that_is_off_is_listed_apart(self):
        app_registry.deactivate('reviews')
        self.addCleanup(app_registry.activate, 'reviews')
        html = self._get('/dashboard/help/')
        self.assertIn('href="/dashboard/help/reviews/"', self._section(html, 'data-help-off'))

    def test_every_installed_app_has_a_page(self):
        for inst in app_registry.all_plugins():
            with self.subTest(app=inst.name):
                self._get(f'/dashboard/help/{inst.name}/')

    def test_an_app_page_works_while_the_app_is_off(self):
        for name in _OFF_SAMPLE:
            with self.subTest(app=name):
                app_registry.deactivate(name)
                try:
                    html = self._get(f'/dashboard/help/{name}/')
                finally:
                    app_registry.activate(name)
                self.assertIn('<span class="pill pill-neutral">Off</span>', html)
                self.assertIn('This app is switched off.', html)

    def test_a_guide_renders_and_its_markers_link(self):
        html = self._get('/dashboard/help/release_notes/')
        self.assertIn('<h2>What it&#x27;s for</h2>', html)
        self.assertIn('href="/dashboard/apps/release_notes/version/"', html)

    def test_an_app_without_a_guide_says_so(self):
        with mock.patch('plugins.app_help.guide', return_value=None):
            html = self._get('/dashboard/help/reviews/')
        self.assertIn('This app has no guide yet.', html)

    def test_where_to_find_it_and_what_linda_can_do(self):
        html = self._get('/dashboard/help/reviews/')
        self.assertIn(
            '<a href="/dashboard/reviews/">Products › Reviews</a>',
            self._section(html, 'data-help-places'),
        )
        tools = self._section(html, 'data-help-tools')
        self.assertIn('What Linda can do here', tools)
        self.assertIn('asks you first', tools)

    def test_a_broken_manifest_still_has_a_page(self):
        inst = app_registry.get('reviews')
        with mock.patch.object(
            type(inst), 'contribute_dashboard_pages', side_effect=RuntimeError('boom')
        ):
            self._get('/dashboard/help/reviews/')

    def test_a_label_with_markup_is_escaped(self):
        inst = app_registry.get('reviews')
        with mock.patch.object(type(inst), 'label', 'Reviews <b>&</b>'):
            for url in ('/dashboard/help/', '/dashboard/help/reviews/'):
                html = self._get(url)
                self.assertIn('Reviews &lt;b&gt;&amp;&lt;/b&gt;', html)
                self.assertNotIn('Reviews <b>&</b>', html)

    def test_an_unknown_app_is_404(self):
        for name in ('no_such_app', 'REVIEWS'):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(f'/dashboard/help/{name}/').status_code, 404)
        self.assertEqual(self.client.get('/dashboard/help/../etc/').status_code, 404)

    def test_signed_out_visitors_are_sent_to_sign_in(self):
        self.client.logout()
        self.assertEqual(self.client.get('/dashboard/help/').status_code, 302)

    def test_staff_without_a_role_read_help_while_roles_are_enforced(self):
        _set_roles('enforce')
        self.addCleanup(app_registry.get('rbac').invalidate_config_cache)
        self._get('/dashboard/help/')
        self._get('/dashboard/help/reviews/')

    def test_the_old_address_redirects(self):
        resp = self.client.get('/dashboard/apps/release_notes/help/')
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp['Location'], '/dashboard/help/')
