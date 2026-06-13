"""Per-visitor merchandising — rank_for_visitor + PRODUCT_LIST_REORDER filter."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.personalisation.services import rank_for_visitor


def _product(slug, sku):
    return Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=sku,
        price=Money(Decimal('10.00'), 'USD'),
        product_type='simple',
        status='active',
    )


def _embed(product, vector):
    from plugins.installed.ai_assistant.models import ProductEmbedding

    # A post_save signal may have already created an embedding row — overwrite it.
    ProductEmbedding.objects.update_or_create(
        product=product,
        defaults={'vector': vector, 'dim': len(vector), 'model': 'test'},
    )


def _viewed(cookie_id, product):
    """Record a product_view for a visitor's analytics session."""
    from plugins.installed.analytics.models import AnalyticsEvent, AnalyticsSession

    session, _ = AnalyticsSession.objects.get_or_create(cookie_id=cookie_id)
    AnalyticsEvent.objects.create(
        name='product.viewed', kind='product_view', session=session, product_slug=product.slug
    )


def _request(*, consent=True, cookie_id='visitor-1'):
    cookies = {'morph_aid': cookie_id}
    if consent:
        cookies['morph_consent'] = '{"functional": true}'
    req = RequestFactory().get('/')
    req.COOKIES.update(cookies)
    return req


class RankForVisitorTests(TestCase):
    def setUp(self):
        # Anchor (viewed) close to B, far from C.
        self.anchor = _product('anchor', 'AN-1')
        self.b = _product('book-b', 'B-1')
        self.c = _product('book-c', 'C-1')
        _embed(self.anchor, [1.0, 0.0, 0.0])
        _embed(self.b, [0.95, 0.05, 0.0])  # similar to anchor
        _embed(self.c, [0.0, 0.0, 1.0])  # dissimilar
        _viewed('visitor-1', self.anchor)

    def test_reorders_similar_first(self):
        # Input order puts the dissimilar book first; ranking should flip it.
        out = rank_for_visitor(_request(), [self.c, self.b], surface='facet')
        self.assertEqual([p.slug for p in out], ['book-b', 'book-c'])

    def test_no_consent_keeps_order(self):
        out = rank_for_visitor(_request(consent=False), [self.c, self.b], surface='facet')
        self.assertEqual([p.slug for p in out], ['book-c', 'book-b'])

    def test_no_history_keeps_order(self):
        out = rank_for_visitor(_request(cookie_id='stranger'), [self.c, self.b], surface='facet')
        self.assertEqual([p.slug for p in out], ['book-c', 'book-b'])

    def test_single_item_noop(self):
        out = rank_for_visitor(_request(), [self.c], surface='facet')
        self.assertEqual(out, [self.c])

    def test_non_product_list_passthrough(self):
        dicts = [{'slug': 'x'}, {'slug': 'y'}]
        self.assertEqual(rank_for_visitor(_request(), dicts, surface='facet'), dicts)


class FilterHookWiringTests(TestCase):
    def test_filter_reorders_when_personalisation_active(self):
        from core.hooks import MorpheusEvents, hook_registry

        anchor = _product('a2', 'A2')
        b = _product('b2', 'B2')
        c = _product('c2', 'C2')
        _embed(anchor, [1.0, 0.0, 0.0])
        _embed(b, [0.95, 0.05, 0.0])
        _embed(c, [0.0, 0.0, 1.0])
        _viewed('v2', anchor)
        req = _request(cookie_id='v2')

        out = hook_registry.filter(
            MorpheusEvents.PRODUCT_LIST_REORDER, value=[c, b], request=req, surface='facet'
        )
        self.assertEqual([p.slug for p in out], ['b2', 'c2'])
