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
    from plugins.installed.returns_portal.plugin import ReturnsPortalPlugin

    assert ReturnsPortalPlugin.name == 'returns_portal'
    assert 'orders' in ReturnsPortalPlugin.requires


def test_default_resolution_is_exchange():
    from plugins.installed.returns_portal.plugin import ReturnsPortalPlugin

    schema = ReturnsPortalPlugin().get_config_schema()
    assert schema['properties']['default_resolution']['default'] == 'exchange'


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
