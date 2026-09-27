"""Smoke tests for the topbar quick-search JSON endpoint.

The endpoint must never 500 (the topbar fetches it on every keystroke
in the search overlay), must enforce the 2-char minimum to avoid
returning the whole catalog on a single letter, and must return a
stable {results: [...]} shape every caller can rely on.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product


class QuickSearchTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Two active products + one draft (draft should NOT appear)
        Product.objects.create(
            name='Confessions of an English Opium-Eater',
            slug='confessions-test',
            sku='C-T-1',
            status='active',
            price=Money(Decimal('10.00'), 'USD'),
            product_type='simple',
        )
        Product.objects.create(
            name='Confidence Book',
            slug='confidence-test',
            sku='C-T-2',
            status='active',
            price=Money(Decimal('12.00'), 'USD'),
            product_type='simple',
        )
        Product.objects.create(
            name='Confidential Draft',
            slug='confidential-draft',
            sku='C-T-3',
            status='draft',
            price=Money(Decimal('9.00'), 'USD'),
            product_type='simple',
        )

    def _fetch(self, q):
        return self.client.get('/api/quick-search/', {'q': q})

    def test_empty_query_returns_empty_results(self):
        resp = self._fetch('')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'results': []})

    def test_single_char_returns_empty_results(self):
        """Without the 2-char floor the topbar would 500-cascade the
        catalog on every keystroke."""
        resp = self._fetch('c')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'results': []})

    def test_response_shape_is_stable(self):
        resp = self._fetch('confessions')
        self.assertEqual(resp.status_code, 200)
        # Must be JSON with a top-level 'results' key — every caller relies on this.
        data = resp.json()
        self.assertIn('results', data)
        self.assertIsInstance(data['results'], list)

    def test_draft_products_excluded(self):
        """status='draft' must never leak via quick-search — it's the
        public-facing autocomplete, not the admin."""
        resp = self._fetch('confidential')
        self.assertEqual(resp.status_code, 200)
        names = [r.get('name') for r in resp.json().get('results', [])]
        self.assertNotIn('Confidential Draft', names)

    def test_each_result_has_required_keys(self):
        """Stable shape — every row needs id/name/slug/price/image_url."""
        resp = self._fetch('confessions')
        for r in resp.json().get('results', []):
            self.assertIn('id', r)
            self.assertIn('name', r)
            self.assertIn('slug', r)
            self.assertIn('price', r)
            self.assertIn('image_url', r)


class QuickSearchPriceTests(TestCase):
    """The dropdown quotes the same price the product card and the PDP quote.

    It read the raw `Product.price` column — which, on a variable product, is
    the parent's `$0.00` the dashboard form writes (per-variant prices are
    canonical there) — and skipped the PRODUCT_CALCULATE_PRICE seam every
    other shopper-facing price goes through.
    """

    def setUp(self):
        from plugins.installed.catalog.models import ProductVariant

        self.product = Product.objects.create(
            name='Variable Probe',
            slug='variable-probe-qs',
            sku='QS-VAR',
            status='active',
            price=Money(Decimal('0.00'), 'USD'),
            product_type='variable',
        )
        for sku, amount in (('QS-VAR-S', '5.00'), ('QS-VAR-L', '8.00')):
            ProductVariant.objects.create(
                product=self.product,
                name=sku,
                sku=sku,
                price=Money(Decimal(amount), 'USD'),
            )

    def _prices(self):
        # An exact SKU hit is the one match tier that needs no search backend.
        results = self.client.get('/api/quick-search/', {'q': 'QS-VAR'}).json()['results']
        return [r['price'] for r in results if r['slug'] == 'variable-probe-qs']

    def test_variable_product_quotes_its_cheapest_variant_not_the_parent_zero(self):
        self.assertEqual(self._prices(), ['$5.00'])

    def test_price_goes_through_the_pricing_seam(self):
        from morpheus.core import MorpheusEvents, hook_registry

        def _rule(value, **kwargs):
            return Money(Decimal('4.00'), 'USD')

        hook_registry.register(MorpheusEvents.PRODUCT_CALCULATE_PRICE, _rule, priority=10)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.PRODUCT_CALCULATE_PRICE, _rule)
        self.assertEqual(self._prices(), ['$4.00'])
