"""The look page the plugin advertises must exist.

lookbook's own description and its PDP block's "See the full look" link both
point at `/looks/<slug>/`, but the plugin shipped with no urls.py and no view —
every one of those links 404'd. These tests pin the page, and the disable
behaviour that makes it a proper contribution.
"""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.catalog.models import Product
from plugins.installed.lookbook.models import Look, LookItem
from plugins.registry import app_registry


class LookDetailTests(TestCase):
    def setUp(self):
        self.look = Look.objects.create(slug='autumn', title='Autumn reading')
        self.p1 = Product.objects.create(
            name='Book One', slug='book-one', sku='LB-1', status='active', price=10
        )
        self.p2 = Product.objects.create(
            name='Book Two', slug='book-two', sku='LB-2', status='active', price=12
        )
        # Deliberately out of order — the page must honour LookItem.order.
        LookItem.objects.create(look=self.look, product=self.p2, order=2)
        LookItem.objects.create(look=self.look, product=self.p1, order=1)

    def test_look_page_renders_its_products(self):
        resp = self.client.get('/looks/autumn/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('Autumn reading', body)
        self.assertIn('Book One', body)
        self.assertIn('Book Two', body)

    def test_products_render_in_author_order(self):
        body = self.client.get('/looks/autumn/').content.decode()
        self.assertLess(body.index('Book One'), body.index('Book Two'))

    def test_unpublished_look_is_404(self):
        Look.objects.filter(pk=self.look.pk).update(is_published=False)
        self.assertEqual(self.client.get('/looks/autumn/').status_code, 404)

    def test_unknown_slug_is_404(self):
        self.assertEqual(self.client.get('/looks/nope/').status_code, 404)

    def test_route_is_dropped_when_the_plugin_is_disabled(self):
        """The route must be registry-gated (the modular-OS disable test).

        Asserted against `get_urlpatterns()` rather than an HTTP request,
        because Django builds the URLconf once per process — a live request
        cannot reflect a runtime deactivate. This is the same shape as
        `core/tests/test_registry_url_disable.py`, and it is what actually
        governs whether the route is served after a restart/reload.
        """
        owned = [
            e
            for e in app_registry._plugin_urls
            if e.get('plugin') == 'lookbook' and e.get('namespace') == 'lookbook'
        ]
        self.assertTrue(owned, 'lookbook should have registered a URL entry')

        app_registry.deactivate('lookbook')
        try:
            self.assertFalse(app_registry.is_active('lookbook'))
            n_off = len(app_registry.get_urlpatterns())
        finally:
            app_registry.activate('lookbook')
        n_on = len(app_registry.get_urlpatterns())
        self.assertGreater(n_on, n_off)
