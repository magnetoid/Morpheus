"""The Lumina landing page is a public marketing page — anyone can view it.
No permission boundary applies (it's not staff/customer-scoped), so the
test asserts it renders 200 within the theme for an anonymous visitor."""

from __future__ import annotations

from django.test import Client, TestCase


class LuminaLandingTests(TestCase):
    def test_landing_public_and_renders(self):
        resp = Client().get('/create/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Lumina')
        self.assertContains(resp, '100 languages')

    def test_features_anchor_target_exists(self):
        # The "Explore features" CTA links to #features — that target must
        # exist, or the button scrolls nowhere (the bug this fixed).
        resp = Client().get('/create/')
        self.assertContains(resp, 'id="features"')

    def test_primary_ctas_launch_the_creator_app(self):
        # Primary CTAs link straight to the Lumina creator app (the view's
        # default), not just an on-page scroll.
        resp = Client().get('/create/')
        self.assertContains(resp, 'https://lumina.dotbooks.store')
