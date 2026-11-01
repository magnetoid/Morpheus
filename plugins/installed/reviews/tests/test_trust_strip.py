"""The trust strip under a product's price (the trust_signals app until v0.129.0).

The storefront PDP passes its blocks the GraphQL product *dict*, not the model.
`collect_trust_data` read `getattr(product, 'pk', None)` — always None on a
dict — and returned `{}`, so the rating / verified-buyer / recent-purchases
strip never appeared on any live PDP, with nothing logged to say why. Its
settings never showed either: the panel's schema had no `properties` wrapper,
so the dashboard rendered no fields.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.utils import translation
from djmoney.money import Money

from plugins.installed.admin_dashboard.views_split.settings import _build_panel_fields
from plugins.installed.catalog.models import Product, Review
from plugins.installed.customers.models import Customer
from plugins.installed.reviews.trust import _plural_window_label
from plugins.models import PluginConfig
from plugins.registry import app_registry


class TrustStripPdpTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.product = Product.objects.create(
            name='Well Reviewed',
            slug='well-reviewed-probe',
            sku='TS-1',
            status='active',
            price=Money(Decimal('12.00'), 'USD'),
        )
        for i in range(3):
            customer = Customer.objects.create_user(
                email=f'reader{i}@example.com', username=f'reader{i}', password='pw-12345678'
            )
            Review.objects.create(
                product=self.product, customer=customer, rating=5, body='Lovely.', is_approved=True
            )

    def test_rating_renders_on_the_pdp(self):
        response = self.client.get('/products/well-reviewed-probe/')
        self.assertEqual(response.status_code, 200)
        # `review-signals__rating` is this block's own class; supernatural's
        # static strip uses `trust-strip__item`, so this cannot match theme markup.
        body = response.content.decode()
        self.assertIn('review-signals__rating', body)
        self.assertIn('(3 reviews)', body)

    def test_a_setting_hides_the_rating(self):
        PluginConfig.objects.update_or_create(
            plugin_name='reviews', defaults={'config': {'show_rating': False}}
        )
        self.addCleanup(app_registry.get('reviews').invalidate_config_cache)
        body = self.client.get('/products/well-reviewed-probe/').content.decode()
        self.assertNotIn('review-signals__rating', body)


class TrustSettingsPanelTests(TestCase):
    def test_the_panel_shows_every_setting(self):
        plugin = app_registry.get('reviews')
        panel = app_registry.settings_panel('reviews')
        keys = [f['key'] for f in _build_panel_fields(plugin, panel.schema)]
        self.assertEqual(
            keys,
            [
                'show_rating',
                'min_reviews_for_rating',
                'show_verified_share',
                'show_recent_purchases',
                'recent_purchases_window_hours',
                'min_recent_purchases',
            ],
        )


class WindowLabelTests(TestCase):
    def test_english(self):
        self.assertEqual(_plural_window_label(72), 'the last 3 days')
        self.assertEqual(_plural_window_label(168), 'the last week')
        self.assertEqual(_plural_window_label(5), 'the last 5 hours')

    def test_serbian(self):
        with translation.override('sr'):
            self.assertEqual(_plural_window_label(72), 'posljednja 3 dana')
            self.assertEqual(_plural_window_label(120), 'posljednjih 5 dana')
