"""What a product page actually claims about the product.

A merchant listing is judged on completeness: identifiers, images, condition,
availability, price validity, ratings. The product page renders a GraphQL
payload — a plain dict — and `product_jsonld` skipped every ORM-only enrichment
when handed one, so the richest page on the site shipped the thinnest markup.
Nothing failed; the properties were simply absent, which is invisible unless
you go and read the JSON-LD.

These tests assert the *presence* of what a merchant listing needs. The
head-parity snapshot only reports losses, so gains like these would otherwise
have no guard at all.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.seo.services import product_jsonld


class ProductMarkupFromRenderedPayloadTests(TestCase):
    """The dict-plus-model path the product page actually uses."""

    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            name='Markup Probe',
            slug='markup-probe',
            sku='MP-1',
            status='active',
            price=Money(Decimal('12.50'), 'USD'),
            short_description='A product that exists to be described.',
        )
        # What the PDP renders: price and stock resolved, nothing else.
        cls.rendered = {
            'slug': 'markup-probe',
            'name': 'Markup Probe',
            'price': {'amount': '12.50', 'currency': 'USD'},
            'short_description': 'A product that exists to be described.',
        }

    def test_the_rendered_payload_alone_still_produces_a_valid_offer(self):
        """The floor: no model row, still a usable listing."""
        node = product_jsonld(self.rendered)
        self.assertEqual(node['@type'], 'Product')
        self.assertEqual(node['offers']['price'], '12.50')
        self.assertEqual(node['offers']['priceCurrency'], 'USD')
        self.assertIn('availability', node['offers'])
        self.assertIn('itemCondition', node['offers'])
        self.assertIn('priceValidUntil', node['offers'])

    def test_the_model_row_supplies_what_a_dict_cannot_carry(self):
        """The fix. Identifiers are the clearest case: a GTIN/ISBN is what lets
        Google match the item to a product it already knows about, and it is
        reachable only through the ORM."""
        from plugins.installed.metafields.models import Metafield

        Metafield.objects.set(
            self.product, namespace='identifiers', key='isbn13', value='9780000000001'
        )

        without_model = product_jsonld(self.rendered)
        with_model = product_jsonld(self.rendered, model=self.product)

        self.assertNotIn('isbn', without_model)
        self.assertEqual(with_model['isbn'], '9780000000001')

    def test_price_and_availability_still_come_from_what_was_rendered(self):
        """The model row must not override the payload: the view loads the
        product with `price` deferred, and markup that disagrees with the
        visible page is precisely what Google forbids."""
        rendered = dict(self.rendered, price={'amount': '9.99', 'currency': 'USD'})
        node = product_jsonld(rendered, model=self.product)
        self.assertEqual(node['offers']['price'], '9.99')

    def test_an_out_of_stock_product_does_not_advertise_in_stock(self):
        """The stock check only ran on the ORM path, so every product page —
        which renders a dict — declared InStock unconditionally."""
        rendered = dict(self.rendered, availability='out_of_stock')
        node = product_jsonld(rendered, model=self.product)
        self.assertEqual(node['offers']['availability'], 'https://schema.org/OutOfStock')

    def test_availability_matches_the_channel_feeds(self):
        """One vocabulary. Markup that disagrees with the feed is a Merchant
        Center mismatch on the same item."""
        from plugins.feed_mapping import availability_to_schema

        rendered = dict(self.rendered, availability='preorder')
        node = product_jsonld(rendered, model=self.product)
        self.assertEqual(node['offers']['availability'], availability_to_schema(rendered))


class ProductGraphOnThePageTests(TestCase):
    """End to end: what the page's `@graph` carries for a product."""

    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            name='Graph Probe',
            slug='graph-probe',
            sku='GP-1',
            status='active',
            price=Money(Decimal('20.00'), 'USD'),
        )

    def _graph(self):
        from core.seo_page import KIND_PRODUCT, SeoPage
        from plugins.installed.seo.schema import build_graph

        page = SeoPage(
            kind=KIND_PRODUCT,
            obj=self.product,
            rendered={
                'slug': 'graph-probe',
                'name': 'Graph Probe',
                'price': {'amount': '20.00', 'currency': 'USD'},
            },
            path='/products/graph-probe/',
            title='Graph Probe',
        )
        return build_graph(page) or {}

    def test_the_product_node_is_built_from_both_sources(self):
        from plugins.installed.metafields.models import Metafield

        Metafield.objects.set(self.product, namespace='identifiers', key='mpn', value='MPN-42')
        nodes = self._graph().get('@graph', [])
        product = next((n for n in nodes if 'Product' in str(n.get('@type', ''))), None)
        self.assertIsNotNone(product, 'the graph has no Product node')
        self.assertEqual(product['offers']['price'], '20.00')
        self.assertEqual(product['mpn'], 'MPN-42')

    def test_exactly_one_node_claims_to_be_the_product(self):
        nodes = self._graph().get('@graph', [])
        product_nodes = [n for n in nodes if 'Product' in str(n.get('@type', ''))]
        self.assertEqual(len(product_nodes), 1, 'the page describes the product twice')


class RatingClaimTests(TestCase):
    """A star rating is a claim about what the page shows."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model

        from plugins.installed.catalog.models import Review

        cls.product = Product.objects.create(
            name='Rating Probe',
            slug='rating-probe',
            sku='RT-1',
            status='active',
            price=Money(Decimal('15.00'), 'USD'),
        )
        # One review per customer per product, hence two shoppers.
        approver = get_user_model().objects.create_user(
            username='rating-shown', email='shown@example.test', password='pw'
        )
        holder = get_user_model().objects.create_user(
            username='rating-held', email='held@example.test', password='pw'
        )
        # One review the page shows, one it does not.
        Review.objects.create(
            product=cls.product, customer=approver, rating=5, body='Shown.', is_approved=True
        )
        Review.objects.create(
            product=cls.product, customer=holder, rating=1, body='Held back.', is_approved=False
        )

    def test_the_rating_counts_only_reviews_the_page_shows(self):
        """The aggregate counted every row while the Review nodes filtered to
        approved, so a page could advertise 3.0 stars from two reviews while
        displaying one five-star review. Google's review policy is explicit
        that markup must reflect the page."""
        node = product_jsonld({'slug': 'rating-probe'}, model=self.product)
        rating = node.get('aggregateRating') or {}

        self.assertEqual(rating.get('reviewCount'), 1)
        self.assertEqual(rating.get('ratingValue'), 5.0)
