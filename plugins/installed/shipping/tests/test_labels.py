"""Carrier labels for an order's parcels (``shipping/labels.py``, v0.154.0).

Shippo and EasyPost are never called: ``requests.post`` is replaced by a fake
that answers like each service's documented API.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from djmoney.money import Money

ORIGIN = {
    'name': 'Warehouse',
    'street1': 'Obala 1',
    'city': 'Kotor',
    'zip': '85330',
    'country': 'ME',
}
ADDRESS = {
    'first_name': 'Ana',
    'last_name': 'Buyer',
    'address_line1': 'Hauptstr. 5',
    'city': 'Berlin',
    'postal_code': '10115',
    'country': 'DE',
}


class _Answer:
    def __init__(self, data, status=200):
        self._data, self.status_code, self.text = data, status, str(data)

    def json(self):
        return self._data


def _shippo(*, txn=None, status=200):
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        if status != 200:
            return _Answer({'detail': 'shippo internal reason'}, status)
        if url.endswith('/shipments/'):
            return _Answer(
                {
                    'rates': [
                        {
                            'object_id': 'r-express',
                            'amount': '12.40',
                            'currency': 'EUR',
                            'provider': 'DHL',
                            'servicelevel': {'name': 'Express'},
                        },
                        {
                            'object_id': 'r-cheap',
                            'amount': '6.10',
                            'currency': 'EUR',
                            'provider': 'Deutsche Post',
                            'servicelevel': {'name': 'Paket'},
                        },
                    ]
                }
            )
        return _Answer(
            txn
            or {
                'status': 'SUCCESS',
                'object_id': 'tx-1',
                'label_url': 'https://shippo.example/label.pdf',
                'tracking_number': 'DP123',
                'tracking_url_provider': 'https://track.example/DP123',
            }
        )

    return post, calls


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
)
class LabelTests(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Product
        from plugins.installed.orders.models import Order, OrderItem
        from plugins.models import PluginConfig

        PluginConfig.objects.update_or_create(
            plugin_name='shipping',
            defaults={
                'config': {'shippo_api_key': 'shippo_test', 'shippo_default_address': ORIGIN}
            },
        )
        self.lamp = Product.objects.create(
            name='Lamp',
            slug='lb-lamp',
            sku='LB-LAMP',
            price=Money(20, 'EUR'),
            weight=Decimal('0.8'),
        )
        self.order = Order.objects.create(
            email='ana@example.com',
            subtotal=Money(40, 'EUR'),
            total=Money(40, 'EUR'),
            status='processing',
            payment_status='paid',
            shipping_address=ADDRESS,
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            product=self.lamp,
            product_name='Lamp',
            sku='LB-LAMP',
            quantity=2,
            unit_price=Money(20, 'EUR'),
            total_price=Money(40, 'EUR'),
        )

    def _commit(self, fn, *args, **kwargs):
        with self.captureOnCommitCallbacks(execute=True):
            return fn(*args, **kwargs)

    def test_ship_with_label_records_the_parcel_with_its_tracking(self):
        from plugins.installed.shipping.labels import ship_with_label

        post, calls = _shippo()
        with mock.patch('requests.post', post):
            label = self._commit(ship_with_label, self.order)

        self.assertEqual(label.tracking_number, 'DP123')
        self.assertEqual((label.carrier, label.service), ('Deutsche Post', 'Paket'))
        self.assertEqual((label.cost_amount, label.cost_currency), (Decimal('6.10'), 'EUR'))
        self.assertEqual(self.order.status, 'shipped')
        parcel = label.fulfillment
        self.assertEqual(parcel.tracking_number, 'DP123')
        self.assertEqual(parcel.items.get().quantity, 2)
        shipment = calls[0][1]['json']
        self.assertEqual(shipment['parcels'][0]['weight'], '1600')
        self.assertEqual(shipment['address_to']['zip'], '10115')
        self.assertEqual(calls[0][1]['headers'], {'Authorization': 'ShippoToken shippo_test'})
        self.assertEqual(calls[1][1]['json']['rate'], 'r-cheap')
        (email,) = [m for m in mail.outbox if 'on its way' in m.subject]
        self.assertIn('DP123', email.body)

    def test_a_label_for_a_recorded_parcel_sends_its_tracking_once(self):
        from plugins.installed.orders.fulfilment import create_fulfillment
        from plugins.installed.shipping.labels import LabelError, label_for_parcel

        parcel = self._commit(create_fulfillment, self.order, {str(self.item.pk): 1})
        mail.outbox.clear()
        post, calls = _shippo()
        with mock.patch('requests.post', post):
            self._commit(label_for_parcel, parcel)
            with self.assertRaisesMessage(LabelError, 'already has a label'):
                label_for_parcel(parcel)
        self.assertEqual(len(calls), 2)
        parcel.refresh_from_db()
        self.assertEqual(parcel.tracking_number, 'DP123')
        (email,) = mail.outbox
        self.assertEqual(email.subject, f'Tracking for order #{self.order.order_number}')
        self.assertIn('DP123', email.body)

    def test_a_parcel_with_tracking_keeps_it_and_sends_nothing(self):
        from plugins.installed.orders.fulfilment import create_fulfillment
        from plugins.installed.shipping.labels import label_for_parcel

        parcel = self._commit(
            create_fulfillment, self.order, {str(self.item.pk): 1}, tracking_number='OWN-1'
        )
        mail.outbox.clear()
        post, _calls = _shippo()
        with mock.patch('requests.post', post):
            self._commit(label_for_parcel, parcel)
        parcel.refresh_from_db()
        self.assertEqual(parcel.tracking_number, 'OWN-1')
        self.assertEqual(mail.outbox, [])

    def test_a_refusal_buys_and_records_nothing(self):
        from plugins.installed.shipping.labels import LabelError, ship_with_label
        from plugins.installed.shipping.models import ShippingLabel

        post, _calls = _shippo(status=400)
        with mock.patch('requests.post', post), self.assertRaises(LabelError) as caught:
            ship_with_label(self.order)
        self.assertIn('HTTP 400', str(caught.exception))
        self.assertNotIn('internal reason', str(caught.exception))
        self.assertFalse(ShippingLabel.objects.exists())
        self.assertFalse(self.order.fulfillments.exists())

    def test_a_failed_transaction_says_why(self):
        from plugins.installed.shipping.labels import LabelError, ship_with_label

        post, _calls = _shippo(
            txn={'status': 'ERROR', 'messages': [{'text': 'Recipient address invalid'}]}
        )
        with (
            mock.patch('requests.post', post),
            self.assertRaisesMessage(LabelError, 'Recipient address invalid'),
        ):
            ship_with_label(self.order)
        self.assertFalse(self.order.fulfillments.exists())

    def test_a_paid_label_is_kept_when_the_parcel_cannot_be_recorded(self):
        from plugins.installed.orders.fulfilment import FulfilmentError
        from plugins.installed.shipping.labels import LabelError, ship_with_label
        from plugins.installed.shipping.models import ShippingLabel

        post, _calls = _shippo()
        boom = mock.Mock(side_effect=FulfilmentError('This order changed meanwhile'))
        with (
            mock.patch('requests.post', post),
            mock.patch('plugins.installed.orders.fulfilment.create_fulfillment', boom),
            self.assertRaisesMessage(LabelError, 'kept on the order'),
        ):
            ship_with_label(self.order)
        label = ShippingLabel.objects.get()
        self.assertIsNone(label.fulfillment)
        self.assertEqual(label.order, self.order)

    def test_an_order_that_cannot_ship_buys_nothing(self):
        from plugins.installed.orders.models import Order
        from plugins.installed.shipping.labels import LabelError, ship_with_label
        from plugins.installed.shipping.models import ShippingLabel

        post = mock.Mock()
        with mock.patch('requests.post', post):
            loaded = Order.objects.get(pk=self.order.pk)
            Order.objects.filter(pk=self.order.pk).update(status='cancelled')
            with self.assertRaisesMessage(LabelError, 'changed meanwhile'):
                ship_with_label(loaded)
            with self.assertRaisesMessage(LabelError, 'cannot ship a parcel'):
                ship_with_label(Order.objects.get(pk=self.order.pk))
        post.assert_not_called()
        self.assertFalse(ShippingLabel.objects.exists())

    def test_any_failure_after_the_purchase_keeps_the_label(self):
        from plugins.installed.shipping.labels import LabelError, ship_with_label
        from plugins.installed.shipping.models import ShippingLabel

        post, _calls = _shippo()
        boom = mock.Mock(side_effect=RuntimeError('the database went away'))
        with (
            mock.patch('requests.post', post),
            mock.patch('plugins.installed.orders.fulfilment.create_fulfillment', boom),
            self.assertRaisesMessage(LabelError, 'kept on the order'),
        ):
            ship_with_label(self.order)
        label = ShippingLabel.objects.get()
        self.assertEqual((label.status, label.tracking_number), ('bought', 'DP123'))
        self.assertIsNone(label.fulfillment)

    def test_an_unfinished_label_is_kept_unconfirmed_and_the_parcel_can_try_again(self):
        from plugins.installed.orders.fulfilment import create_fulfillment
        from plugins.installed.shipping.labels import LabelUnconfirmed, label_for_parcel
        from plugins.installed.shipping.models import ShippingLabel

        parcel = self._commit(create_fulfillment, self.order, {str(self.item.pk): 1})
        post, _calls = _shippo(txn={'status': 'QUEUED', 'object_id': 'tx-q'})
        with mock.patch('requests.post', post), self.assertRaises(LabelUnconfirmed) as caught:
            label_for_parcel(parcel)
        self.assertIn('Check your Shippo account', str(caught.exception))
        kept = ShippingLabel.objects.get()
        self.assertEqual(
            (kept.status, kept.provider_id, kept.fulfillment), ('unconfirmed', 'tx-q', None)
        )

        post, _calls = _shippo()
        with mock.patch('requests.post', post):
            self._commit(label_for_parcel, parcel)
        self.assertTrue(ShippingLabel.objects.filter(status='bought', fulfillment=parcel).exists())

    def test_no_answer_to_the_purchase_is_unconfirmed(self):
        import requests

        from plugins.installed.shipping.labels import LabelUnconfirmed, ship_with_label
        from plugins.installed.shipping.models import ShippingLabel

        shippo, _calls = _shippo()

        def post(url, **kwargs):
            if url.endswith('/transactions/'):
                raise requests.Timeout('slow')
            return shippo(url, **kwargs)

        with mock.patch('requests.post', post), self.assertRaises(LabelUnconfirmed):
            ship_with_label(self.order)
        self.assertEqual(ShippingLabel.objects.get().status, 'unconfirmed')
        self.assertFalse(self.order.fulfillments.exists())

    def test_a_second_click_waits_until_the_first_parcel_is_recorded(self):
        from plugins.installed.orders import fulfilment
        from plugins.installed.orders.models import Order
        from plugins.installed.shipping.labels import LabelError, ship_with_label

        post, calls = _shippo()
        real = fulfilment.create_fulfillment
        refused = []

        def between(*args, **kwargs):
            # The label is paid for and stored; the parcel is not recorded yet.
            try:
                ship_with_label(Order.objects.get(pk=self.order.pk))
            except LabelError as exc:
                refused.append(str(exc))
            return real(*args, **kwargs)

        with (
            mock.patch('requests.post', post),
            mock.patch.object(fulfilment, 'create_fulfillment', between),
        ):
            label = ship_with_label(self.order)
        self.assertIn('being bought', refused[0])
        self.assertEqual(len([c for c in calls if c[0].endswith('/transactions/')]), 1)
        self.assertEqual((label.status, label.fulfillment.order_id), ('bought', self.order.pk))

    def test_a_variant_weight_wins_over_its_product(self):
        from plugins.installed.catalog.models import ProductVariant
        from plugins.installed.shipping.labels import ship_with_label

        self.item.variant = ProductVariant.objects.create(
            product=self.lamp, name='Big', sku='LB-LAMP-BIG', price=Money(20, 'EUR'), weight=2
        )
        self.item.save()
        post, calls = _shippo()
        with mock.patch('requests.post', post):
            ship_with_label(self.order)
        shipment = calls[0][1]['json']
        self.assertEqual(shipment['parcels'][0]['weight'], '4000')

    def test_a_gateway_error_on_the_purchase_is_unconfirmed(self):
        from plugins.installed.shipping.labels import LabelUnconfirmed, ship_with_label
        from plugins.installed.shipping.models import ShippingLabel

        shippo, _calls = _shippo()

        def post(url, **kwargs):
            if url.endswith('/transactions/'):
                return _Answer({'detail': 'bad gateway'}, 502)
            return shippo(url, **kwargs)

        with mock.patch('requests.post', post), self.assertRaises(LabelUnconfirmed):
            ship_with_label(self.order)
        self.assertEqual(ShippingLabel.objects.get().status, 'unconfirmed')

    def test_a_bought_label_that_cannot_be_stored_keeps_its_reference(self):
        from plugins.installed.shipping import labels
        from plugins.installed.shipping.models import ShippingLabel

        shippo, _calls = _shippo()
        real = labels._shippo

        def bought(*args):
            return {**real(*args), 'no_such_column': 'x'}  # the update refuses it

        with (
            mock.patch('requests.post', shippo),
            mock.patch.object(labels, '_shippo', bought),
            self.assertRaisesMessage(labels.LabelUnconfirmed, 'do not buy it again'),
        ):
            labels.ship_with_label(self.order)
        label = ShippingLabel.objects.get()
        self.assertEqual((label.status, label.provider_id), ('unconfirmed', 'tx-1'))
        self.assertFalse(self.order.fulfillments.exists())

    def test_a_purchase_in_progress_blocks_another_and_a_cut_off_one_is_reported_once(self):
        from datetime import timedelta

        from django.utils import timezone

        from plugins.installed.shipping.labels import LabelError, ship_with_label
        from plugins.installed.shipping.models import ShippingLabel

        running = ShippingLabel.objects.create(order=self.order, provider='shippo')
        post = mock.Mock()
        with mock.patch('requests.post', post):
            with self.assertRaisesMessage(LabelError, 'being bought'):
                ship_with_label(self.order)
            ShippingLabel.objects.filter(pk=running.pk).update(
                created_at=timezone.now() - timedelta(minutes=10)
            )
            with self.assertRaisesMessage(LabelError, 'did not finish'):
                ship_with_label(self.order)
        post.assert_not_called()
        running.refresh_from_db()
        self.assertEqual(running.status, 'unconfirmed')

        post, _calls = _shippo()
        with mock.patch('requests.post', post):
            label = self._commit(ship_with_label, self.order)
        self.assertEqual(label.status, 'bought')

    def test_easypost_buys_the_cheapest_rate(self):
        from plugins.installed.shipping.labels import ship_with_label
        from plugins.models import PluginConfig

        PluginConfig.objects.filter(plugin_name='shipping').update(
            config={'easypost_api_key': 'ep_test', 'easypost_default_address': ORIGIN}
        )
        calls = []

        def post(url, **kwargs):
            calls.append((url, kwargs))
            if url.endswith('/v2/shipments'):
                return _Answer(
                    {
                        'id': 'shp_1',
                        'rates': [
                            {'id': 'rate_b', 'rate': '11.00', 'currency': 'EUR', 'carrier': 'UPS'},
                            {
                                'id': 'rate_a',
                                'rate': '8.00',
                                'currency': 'EUR',
                                'carrier': 'DHL',
                                'service': 'Paket',
                            },
                        ],
                    }
                )
            return _Answer(
                {
                    'id': 'shp_1',
                    'postage_label': {'label_url': 'https://ep.example/l.pdf'},
                    'tracking_code': 'EZ1',
                    'tracker': {'public_url': 'https://track.easypost.example/EZ1'},
                }
            )

        with mock.patch('requests.post', post):
            label = self._commit(ship_with_label, self.order)
        self.assertEqual(
            (label.provider, label.tracking_number, label.carrier), ('easypost', 'EZ1', 'DHL')
        )
        self.assertEqual(calls[1][0], 'https://api.easypost.com/v2/shipments/shp_1/buy')
        self.assertEqual(calls[1][1]['json'], {'rate': {'id': 'rate_a'}})
        self.assertEqual(calls[0][1]['auth'], ('ep_test', ''))

    def test_refusals_before_any_purchase(self):
        from plugins.installed.shipping.labels import LabelError, ship_with_label
        from plugins.models import PluginConfig

        post = mock.Mock()
        with mock.patch('requests.post', post):
            self.order.shipping_address = {'country': 'DE'}
            self.order.save(update_fields=['shipping_address'])
            with self.assertRaisesMessage(LabelError, 'no full shipping address'):
                ship_with_label(self.order)
            PluginConfig.objects.filter(plugin_name='shipping').update(config={})
            with self.assertRaisesMessage(LabelError, 'Set up Shippo or EasyPost'):
                ship_with_label(self.order)
        post.assert_not_called()


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
)
class LabelPanelAndViewTests(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Product
        from plugins.installed.orders.models import Order, OrderItem
        from plugins.models import PluginConfig

        PluginConfig.objects.update_or_create(
            plugin_name='shipping',
            defaults={
                'config': {'shippo_api_key': 'shippo_test', 'shippo_default_address': ORIGIN}
            },
        )
        self.staff = get_user_model().objects.create_user(
            username='ops', email='ops@example.com', password='x', is_staff=True, is_superuser=True
        )
        mug = Product.objects.create(name='Mug', slug='lp-mug', sku='LP-MUG', price=Money(5, 'EUR'))
        self.order = Order.objects.create(
            email='ana@example.com',
            subtotal=Money(5, 'EUR'),
            total=Money(5, 'EUR'),
            status='processing',
            payment_status='paid',
            shipping_address=ADDRESS,
        )
        OrderItem.objects.create(
            order=self.order,
            product=mug,
            product_name='Mug',
            sku='LP-MUG',
            quantity=1,
            unit_price=Money(5, 'EUR'),
            total_price=Money(5, 'EUR'),
        )
        self.buy_url = f'/dashboard/shipping/labels/{self.order.order_number}/buy/'

    def _page(self):
        self.client.force_login(self.staff)
        return self.client.get(f'/dashboard/orders/{self.order.order_number}/').content.decode()

    def test_the_order_page_offers_a_label_while_a_carrier_is_set_up(self):
        from plugins.models import PluginConfig

        self.assertIn('Ship everything left with a label', self._page())
        PluginConfig.objects.filter(plugin_name='shipping').update(config={})
        self.assertNotIn('Shipping labels', self._page())

    def test_anonymous_and_customers_cannot_buy(self):
        post, calls = _shippo()
        customer = get_user_model().objects.create_user(
            username='c', email='c@example.com', password='x'
        )
        with mock.patch('requests.post', post):
            self.assertEqual(self.client.post(self.buy_url).status_code, 302)
            self.client.force_login(customer)
            self.assertEqual(self.client.post(self.buy_url).status_code, 302)
        self.assertEqual(calls, [])

    def test_staff_buy_from_the_panel(self):
        from plugins.installed.shipping.models import ShippingLabel

        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.buy_url).status_code, 405)
        post, _calls = _shippo()
        with mock.patch('requests.post', post), self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.buy_url, follow=True)
        self.assertContains(response, 'Label bought from Shippo, tracking DP123.')
        self.assertContains(response, 'Open label')
        self.assertEqual(ShippingLabel.objects.get().order, self.order)

    def test_linda_buys_a_label_for_a_parcel(self):
        from morpheus.core import ToolError
        from plugins.installed.orders.fulfilment import create_fulfillment
        from plugins.installed.shipping.agent_tools import buy_label_tool

        with self.captureOnCommitCallbacks(execute=True):
            parcel = create_fulfillment(self.order)
        post, _calls = _shippo()
        with mock.patch('requests.post', post), self.captureOnCommitCallbacks(execute=True):
            result = buy_label_tool.invoke(
                {'order_number': self.order.order_number, 'parcel': str(parcel.pk)}
            )
        self.assertEqual(result.output['tracking_number'], 'DP123')
        self.assertEqual(result.output['parcel'], str(parcel.pk))
        for parcel_id in ('00000000-0000-0000-0000-000000000000', 'not-a-uuid'):
            with self.subTest(parcel=parcel_id), self.assertRaisesMessage(ToolError, 'no parcel'):
                buy_label_tool.invoke(
                    {'order_number': self.order.order_number, 'parcel': parcel_id}
                )

    def test_a_malformed_parcel_id_is_not_found(self):
        self.client.force_login(self.staff)
        response = self.client.post(self.buy_url, {'fulfillment': 'not-a-uuid'})
        self.assertEqual(response.status_code, 404)

    def test_the_panel_names_an_unconfirmed_label(self):
        from plugins.installed.shipping.models import ShippingLabel

        ShippingLabel.objects.create(
            order=self.order, provider='shippo', status='unconfirmed', provider_id='tx-q'
        )
        page = self._page()
        self.assertIn('was not confirmed (reference tx-q)', page)
        self.assertIn('Check your Shippo account', page)
