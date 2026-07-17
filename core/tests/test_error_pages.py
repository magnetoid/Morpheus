"""Branded 404/500 pages + favicon — the "professional storefront" floor.

The templates live in the global templates/ dir (not the theme) so any active
theme gets a branded error page; Django resolves the root names 404.html /
500.html only when DEBUG is off (always off under tests).
"""

from django.template import loader
from django.test import TestCase


class ErrorPageTests(TestCase):
    def test_404_renders_branded_page(self):
        resp = self.client.get('/definitely-not-a-real-page-xyz/')
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, 'gone missing', status_code=404)
        # dead-ends must offer a way out
        self.assertContains(resp, 'Browse all books', status_code=404)

    def test_404_is_noindexed(self):
        resp = self.client.get('/definitely-not-a-real-page-xyz/')
        self.assertContains(resp, 'noindex', status_code=404)

    def test_500_template_renders_with_empty_context(self):
        # django.views.defaults.server_error renders 500.html with an EMPTY
        # context — no request, no context processors. Rendering it bare is
        # exactly the production condition; any {% extends %}/{% static %}/
        # variable dependency would blow up here.
        html = loader.render_to_string('500.html')
        self.assertIn('tipped over', html)
        self.assertIn('href="/"', html)

    def test_favicon_served_at_conventional_path(self):
        resp = self.client.get('/favicon.ico')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'image/svg+xml')
        self.assertIn('public', resp['Cache-Control'])
