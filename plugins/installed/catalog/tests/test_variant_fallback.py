"""Variant copy + display-price fallback tests.

Guards the two recent fixes (commits cd1dde1 + 86de224 + 9ebcff5) so a
future change can't silently re-break them:

  1. Product.display_price returns min(variant.effective_price) for
     Variable products with active variants; falls back to self.price
     otherwise.
  2. Product.price_starts_from is True only when 2+ active variants
     (so single-variant products don't render an awkward "From").
  3. GraphQL ProductVariantType.short_description / description fall
     back to the parent Product's matching field when blank, but
     return the variant's own value when set.
  4. GraphQL ProductVariantType.price falls back to the parent product
     price when the variant has none.
"""
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money


def _make_product(**overrides):
    from plugins.installed.catalog.models import Product
    defaults = {
        'name': 'A Book',
        'slug': 'a-book',
        'sku': 'BK-1',
        'status': 'active',
        'price': Money(Decimal('20.00'), 'USD'),
        'short_description': 'A short.',
        'description': 'A long.',
        'product_type': 'simple',
    }
    defaults.update(overrides)
    return Product.objects.create(**defaults)


def _make_variant(product, **overrides):
    from plugins.installed.catalog.models import ProductVariant
    defaults = {
        'product': product,
        'name': 'V1',
        'sku': product.sku + '-V1',
        'is_active': True,
    }
    defaults.update(overrides)
    return ProductVariant.objects.create(**defaults)


class DisplayPriceTests(TestCase):
    def test_simple_product_returns_own_price(self):
        p = _make_product(price=Money(Decimal('15.00'), 'USD'))
        self.assertEqual(p.display_price.amount, Decimal('15.00'))
        self.assertFalse(p.price_starts_from)

    def test_variable_returns_min_variant_price(self):
        p = _make_product(
            slug='var-book', sku='BK-V',
            product_type='variable', price=Money(Decimal('0.00'), 'USD'),
        )
        _make_variant(p, sku='BK-V-A', price=Money(Decimal('30.00'), 'USD'))
        _make_variant(p, sku='BK-V-B', name='V2', price=Money(Decimal('12.00'), 'USD'))
        _make_variant(p, sku='BK-V-C', name='V3', price=Money(Decimal('25.00'), 'USD'))

        self.assertEqual(p.display_price.amount, Decimal('12.00'))
        self.assertTrue(p.price_starts_from)

    def test_variable_single_variant_no_from_prefix(self):
        p = _make_product(
            slug='var-book-single', sku='BK-VS',
            product_type='variable', price=Money(Decimal('0.00'), 'USD'),
        )
        _make_variant(p, sku='BK-VS-A', price=Money(Decimal('18.00'), 'USD'))
        self.assertEqual(p.display_price.amount, Decimal('18.00'))
        # "From" prefix is awkward when there's only one option to pick.
        self.assertFalse(p.price_starts_from)

    def test_variable_inactive_variants_excluded(self):
        p = _make_product(
            slug='var-inactive', sku='BK-VI',
            product_type='variable', price=Money(Decimal('0.00'), 'USD'),
        )
        _make_variant(p, sku='BK-VI-A', price=Money(Decimal('99.00'), 'USD'))
        _make_variant(p, sku='BK-VI-B', name='V2',
                      price=Money(Decimal('5.00'), 'USD'), is_active=False)
        # The $5 variant is inactive so the min should be $99, not $5.
        self.assertEqual(p.display_price.amount, Decimal('99.00'))


class VariantCopyFallbackTests(TestCase):
    """The GraphQL ProductVariantType.short_description / description
    resolvers fall back to the parent product's value when the variant's
    own copy is blank. Tested directly against the resolver class —
    no need to spin up a full Strawberry schema for unit coverage.
    """

    def _get_resolver(self, attr):
        from plugins.installed.catalog.graphql.types import ProductVariantType
        # Methods are decorated @strawberry.field; the underlying callable
        # lives on the class. Resolve via __dict__ rather than getattr to
        # bypass strawberry's wrapping.
        for source_attr in (attr, f'_{attr}'):
            cls_attr = ProductVariantType.__dict__.get(source_attr)
            if cls_attr is None:
                continue
            wrapped = getattr(cls_attr, 'base_resolver', None) or cls_attr
            if callable(wrapped):
                return wrapped
        # Fall back to direct attribute lookup.
        return ProductVariantType.__dict__[attr]

    def test_short_description_falls_back_to_parent(self):
        p = _make_product(
            slug='copy-fb', sku='CFB',
            short_description='Parent short.',
            description='Parent long.',
        )
        v = _make_variant(p, sku='CFB-V1', short_description='', description='')

        resolver = self._get_resolver('short_description')
        result = resolver(v) if hasattr(resolver, '__call__') else resolver.fget(v)
        self.assertEqual(result, 'Parent short.')

    def test_description_keeps_variant_value_when_set(self):
        p = _make_product(slug='copy-keep', sku='CK', description='Parent long.')
        v = _make_variant(p, sku='CK-V1', description='Variant long.')

        resolver = self._get_resolver('description')
        result = resolver(v) if hasattr(resolver, '__call__') else resolver.fget(v)
        self.assertEqual(result, 'Variant long.')


class VariantSalePriceTests(TestCase):
    """GraphQL ProductVariantType exposes compare_at_price / is_on_sale /
    discount_percentage so the PDP picker can show a per-variant sale
    pill + strikethrough was-price. Per-variant overrides win over the
    parent product's compare_at."""

    def _get_resolver(self, attr):
        from plugins.installed.catalog.graphql.types import ProductVariantType
        for source_attr in (attr, f'_{attr}'):
            cls_attr = ProductVariantType.__dict__.get(source_attr)
            if cls_attr is None:
                continue
            return getattr(cls_attr, 'base_resolver', None) or cls_attr
        return ProductVariantType.__dict__[attr]

    def test_is_on_sale_when_variant_has_compare_above_price(self):
        p = _make_product(slug='sale-1', sku='S1')
        v = _make_variant(
            p, sku='S1-V1',
            price=Money(Decimal('12.00'), 'USD'),
            compare_at_price=Money(Decimal('20.00'), 'USD'),
        )
        is_on_sale = self._get_resolver('is_on_sale')(v)
        self.assertTrue(is_on_sale)
        pct = self._get_resolver('discount_percentage')(v)
        # (20 - 12) / 20 = 40%
        self.assertEqual(pct, 40)

    def test_no_sale_when_compare_below_price(self):
        # Misconfigured row — compare_at LOWER than price. Must not
        # render a fake sale pill (would otherwise show "−(negative)%").
        p = _make_product(slug='sale-2', sku='S2')
        v = _make_variant(
            p, sku='S2-V1',
            price=Money(Decimal('25.00'), 'USD'),
            compare_at_price=Money(Decimal('15.00'), 'USD'),
        )
        self.assertFalse(self._get_resolver('is_on_sale')(v))
        self.assertEqual(self._get_resolver('discount_percentage')(v), 0)

    def test_compare_at_falls_back_to_parent_product(self):
        # Variant has no compare_at of its own; parent product does. The
        # resolver should return the parent's value so the strikethrough
        # renders on per-product sales even when the variant is plain.
        p = _make_product(
            slug='sale-3', sku='S3',
            price=Money(Decimal('10.00'), 'USD'),
            compare_at_price=Money(Decimal('18.00'), 'USD'),
        )
        v = _make_variant(p, sku='S3-V1')  # no own price or compare
        cap = self._get_resolver('compare_at_price')(v)
        self.assertIsNotNone(cap)
        self.assertEqual(str(cap.amount), '18.00')
        self.assertTrue(self._get_resolver('is_on_sale')(v))

    def test_no_compare_means_no_sale(self):
        p = _make_product(slug='sale-4', sku='S4')
        v = _make_variant(p, sku='S4-V1', price=Money(Decimal('10.00'), 'USD'))
        self.assertIsNone(self._get_resolver('compare_at_price')(v))
        self.assertFalse(self._get_resolver('is_on_sale')(v))


class FlipbookViewTests(TestCase):
    def test_404_when_product_missing(self):
        from django.test import Client
        resp = Client().get('/p/does-not-exist/flipbook/')
        self.assertEqual(resp.status_code, 404)

    def test_404_when_product_has_no_pdf(self):
        from django.test import Client
        _make_product(slug='no-pdf-book', sku='NPB', product_type='digital')
        resp = Client().get('/p/no-pdf-book/flipbook/')
        self.assertEqual(resp.status_code, 404)
