"""returns_portal extends the CANONICAL orders.ReturnRequest — it must
never redefine the return concept in a parallel table (the original
PR #62 version did exactly that, invisibly to the dashboard returns UI,
RMA numbers, refund service and agent tools).
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money


def test_plugin_metadata():
    from plugins.installed.returns_portal.app import ReturnsPortalPlugin

    assert ReturnsPortalPlugin.name == 'returns_portal'
    assert 'orders' in ReturnsPortalPlugin.requires


def test_no_parallel_return_model():
    # One concept, one owner: the return lives in orders.refunds.
    from plugins.installed.returns_portal import models as portal_models

    assert not hasattr(portal_models, 'ReturnRequest')
    assert not hasattr(portal_models, 'ReturnItem')


class PortalExtensionTests(TestCase):
    def _canonical_return(self):
        from plugins.installed.catalog.models import Product
        from plugins.installed.orders.models import Order, OrderItem
        from plugins.installed.orders.refunds import ReturnService

        user = get_user_model().objects.create_user(username='c', password='x')
        product = Product.objects.create(
            name='Book',
            slug='book-rp',
            sku='B-RP',
            price=Money(Decimal('20'), 'USD'),
            status='active',
        )
        order = Order.objects.create(
            customer=user,
            email='c@example.com',
            subtotal=Money(Decimal('20'), 'USD'),
            total=Money(Decimal('20'), 'USD'),
        )
        item = OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            sku=product.sku,
            quantity=1,
            unit_price=product.price,
            total_price=product.price,
        )
        return ReturnService.create_request(
            order=order,
            items=[{'order_item_id': str(item.id), 'quantity': 1}],
            reason='changed_mind',
        )

    def test_resolution_and_feedback_attach_to_canonical_return(self):
        from plugins.installed.returns_portal.models import ReturnFeedback, ReturnResolution

        rr = self._canonical_return()
        res = ReturnResolution.objects.create(request=rr, resolution='store_credit')
        fb = ReturnFeedback.objects.create(request=rr, nps_score=7)

        rr.refresh_from_db()
        self.assertEqual(rr.portal_resolution, res)
        self.assertEqual(rr.portal_feedback, fb)
        self.assertIn(rr.rma_number, str(res))


class VariantOfferReturnPolicyTests(TestCase):
    """A multi-edition product keeps its offers on `hasVariant`, not the group."""

    def _graph(self):
        return {
            '@graph': [
                {
                    '@type': 'ProductGroup',
                    'hasVariant': [
                        {'@type': 'Product', 'offers': {'@type': 'Offer', 'price': '5.00'}},
                        {'@type': 'Product', 'offers': {'@type': 'Offer', 'price': '9.00'}},
                    ],
                }
            ]
        }

    def _page(self):
        from types import SimpleNamespace

        return SimpleNamespace(obj=SimpleNamespace(product_type='simple', requires_shipping=True))

    def test_every_variant_offer_carries_the_policy(self):
        from core.models import StoreSettings
        from plugins.installed.returns_portal.seo_graph import on_seo_jsonld_graph

        store = StoreSettings.objects.first() or StoreSettings.objects.create()
        store.country = 'US'
        store.save()
        graph = on_seo_jsonld_graph(self._graph(), page=self._page())
        for member in graph['@graph'][0]['hasVariant']:
            policy = member['offers']['hasMerchantReturnPolicy']
            self.assertEqual(policy['applicableCountry'], 'US')
            self.assertEqual(policy['merchantReturnDays'], 30)

    def test_nothing_is_claimed_without_a_country(self):
        from core.models import StoreSettings
        from plugins.installed.returns_portal.seo_graph import on_seo_jsonld_graph

        store = StoreSettings.objects.first() or StoreSettings.objects.create()
        store.country = ''
        store.save()
        graph = on_seo_jsonld_graph(self._graph(), page=self._page())
        for member in graph['@graph'][0]['hasVariant']:
            self.assertNotIn('hasMerchantReturnPolicy', member['offers'])
