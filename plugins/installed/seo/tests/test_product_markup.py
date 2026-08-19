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


class VariantMarkupTests(TestCase):
    """A product sold in several versions is a group, and says so.

    `hasVariant` has existed in this codebase since v0.30 and never ran on a
    product page — it sat behind an ORM-only guard while the page rendered a
    dict. Without it, each edition competes with its siblings instead of being
    presented as one item with choices.
    """

    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import ProductVariant

        cls.product = Product.objects.create(
            name='Variant Probe',
            slug='variant-probe',
            sku='VP-1',
            status='active',
            price=Money(Decimal('16.00'), 'USD'),
        )
        cls.print_variant = ProductVariant.objects.create(
            product=cls.product,
            name='Print',
            sku='VP-1-P',
            variant_type='physical',
            price=Money(Decimal('16.00'), 'USD'),
        )
        cls.digital = ProductVariant.objects.create(
            product=cls.product,
            name='Digital PDF',
            sku='VP-1-D',
            variant_type='digital',
            price=Money(Decimal('9.00'), 'USD'),
        )

    def _node(self):
        return product_jsonld({'slug': 'variant-probe'}, model=self.product)

    def test_a_multi_version_product_is_a_product_group(self):
        node = self._node()
        self.assertEqual(node['@type'], 'ProductGroup')
        self.assertEqual(node['productGroupID'], str(self.product.id))
        self.assertEqual(len(node['hasVariant']), 2)

    def test_each_variant_carries_its_own_price(self):
        prices = {v['sku']: v['offers']['price'] for v in self._node()['hasVariant']}
        self.assertEqual(prices['VP-1-P'], '16.00')
        self.assertEqual(prices['VP-1-D'], '9.00')

    def test_the_group_says_what_it_varies_by(self):
        """Print vs digital is a material difference; claiming an axis the
        variants do not differ on would be worse than claiming none."""
        self.assertEqual(self._node()['variesBy'], 'https://schema.org/bookFormat')

    def test_a_single_variant_is_not_a_group(self):
        """A chooser for one option is a chooser the shopper does not have."""
        self.digital.delete()
        node = self._node()
        self.assertEqual(node['@type'], 'Product')
        self.assertNotIn('hasVariant', node)

    def test_a_variant_out_of_stock_is_not_advertised_as_available(self):
        """Every member used to be hardcoded InStock, so a group whose only
        available option was the ebook still offered the hardcover."""
        from plugins.installed.inventory.models import StockLevel, Warehouse

        self.product.track_inventory = True
        self.product.save(update_fields=['track_inventory'])
        warehouse = Warehouse.objects.create(name='Main', code='VMAIN')
        StockLevel.objects.create(variant=self.print_variant, warehouse=warehouse, quantity=0)
        StockLevel.objects.create(variant=self.digital, warehouse=warehouse, quantity=5)

        availability = {v['sku']: v['offers']['availability'] for v in self._node()['hasVariant']}
        self.assertEqual(availability['VP-1-P'], 'https://schema.org/OutOfStock')
        self.assertEqual(availability['VP-1-D'], 'https://schema.org/InStock')


class SalePriceTests(TestCase):
    """A discount is only a discount if the old price was higher."""

    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            name='Sale Probe',
            slug='sale-probe',
            sku='SL-1',
            status='active',
            price=Money(Decimal('10.00'), 'USD'),
        )

    def test_a_reduced_product_publishes_its_previous_price(self):
        self.product.compare_at_price = Money(Decimal('18.00'), 'USD')
        self.product.save(update_fields=['compare_at_price'])

        spec = product_jsonld({'slug': 'sale-probe'}, model=self.product)['offers'][
            'priceSpecification'
        ]

        self.assertEqual(spec['priceType'], 'https://schema.org/StrikethroughPrice')
        self.assertEqual(spec['price'], '18.00')

    def test_a_compare_at_price_that_is_not_higher_is_not_a_sale(self):
        """A leftover compare-at price equal to the price would advertise a
        saving of nothing."""
        self.product.compare_at_price = Money(Decimal('10.00'), 'USD')
        self.product.save(update_fields=['compare_at_price'])

        offer = product_jsonld({'slug': 'sale-probe'}, model=self.product)['offers']

        self.assertNotIn('priceSpecification', offer)

    def test_no_compare_at_price_means_no_claim(self):
        offer = product_jsonld({'slug': 'sale-probe'}, model=self.product)['offers']
        self.assertNotIn('priceSpecification', offer)


class DeferredFieldTests(TestCase):
    """A view that loads a product with `.only()` must not cost it its markup.

    djmoney raises **KeyError** when one of its fields was not selected, and
    `getattr`'s default only swallows AttributeError. The product page defers
    `price` and `compare_at_price`, so one unguarded read inside the markup
    builder raised, the graph's per-node guard caught it, and the page shipped
    with no Product node at all — a total loss of the product's structured
    data, with a 200 and nothing in the logs above debug.
    """

    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            name='Deferred Probe',
            slug='deferred-probe',
            sku='DF-1',
            status='active',
            price=Money(Decimal('14.00'), 'USD'),
            compare_at_price=Money(Decimal('20.00'), 'USD'),
        )

    def test_a_deferred_money_field_does_not_lose_the_product_node(self):
        deferred = Product.objects.only('id', 'slug', 'name', 'status').get(pk=self.product.pk)

        node = product_jsonld(
            {'slug': 'deferred-probe', 'price': {'amount': '14.00', 'currency': 'USD'}},
            model=deferred,
        )

        self.assertEqual(node['@type'], 'Product')
        self.assertEqual(node['offers']['price'], '14.00')
        # The sale price simply is not known from a row that never loaded it —
        # absent is correct, raising is not.
        self.assertNotIn('priceSpecification', node['offers'])

    def test_the_full_row_still_publishes_the_sale(self):
        node = product_jsonld(
            {'slug': 'deferred-probe', 'price': {'amount': '14.00', 'currency': 'USD'}},
            model=self.product,
        )
        self.assertEqual(node['offers']['priceSpecification']['price'], '20.00')


class BookVariantTypeTests(TestCase):
    """A book sold in several editions is still a group.

    Deduplicating the Book claim (the page carries a dedicated Book node)
    flattened the whole @type list to 'Product', which also erased
    'ProductGroup' — leaving hasVariant, variesBy and productGroupID on a node
    that declared itself a plain Product, so Google ignored all three.
    """

    @classmethod
    def setUpTestData(cls):
        from plugins.installed.book_product.models import BookProduct
        from plugins.installed.catalog.models import ProductVariant

        cls.product = Product.objects.create(
            name='Book Group Probe',
            slug='book-group-probe',
            sku='BG-1',
            status='active',
            price=Money(Decimal('16.00'), 'USD'),
        )
        BookProduct.objects.create(product=cls.product, author='Ines Parityauthor')
        ProductVariant.objects.create(
            product=cls.product, name='Print', sku='BG-1-P', variant_type='physical'
        )
        ProductVariant.objects.create(
            product=cls.product, name='Digital', sku='BG-1-D', variant_type='digital'
        )

    def test_a_multi_edition_book_keeps_its_group_type_beside_a_book_node(self):
        from core.seo_page import KIND_PRODUCT, SeoPage
        from plugins.installed.seo.schema import build_graph

        page = SeoPage(
            kind=KIND_PRODUCT,
            obj=self.product,
            rendered={'slug': 'book-group-probe', 'price': {'amount': '16.00', 'currency': 'USD'}},
            path='/products/book-group-probe/',
            title='Book Group Probe',
            # `authors` (a list) is what book_jsonld requires to emit a node;
            # with a bare `author` it returns {} and the dedup never runs.
            context={
                'book_jsonld_data': {
                    'name': 'Book Group Probe',
                    'authors': ['Ines Parityauthor'],
                    'path': '/products/book-group-probe/',
                }
            },
        )
        nodes = (build_graph(page) or {}).get('@graph', [])
        group = next((n for n in nodes if 'ProductGroup' in str(n.get('@type', ''))), None)

        self.assertIsNotNone(group, 'the multi-edition book lost its ProductGroup type')
        self.assertIn('hasVariant', group)
        # The dedup must actually have run: a standalone Book node exists...
        standalone = [n for n in nodes if n.get('@type') == 'Book']
        self.assertEqual(len(standalone), 1, 'the Book node was not emitted')
        # ...and it is the ONLY thing claiming to be a Book.
        books = [n for n in nodes if 'Book' in str(n.get('@type', ''))]
        self.assertEqual(len(books), 1)
