"""CJdropshipping: client rules, import, sending/paying/tracking orders, webhooks.

The CJ API is faked at the HTTP layer (``requests.request`` / ``requests.post``)
with the response shapes from the official docs, so the client's envelope
handling, token retry and every request body are exercised for real.
"""

from __future__ import annotations

import io
import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from djmoney.money import Money

ADDRESS = {
    'first_name': 'Ada',
    'last_name': 'Lovelace',
    'address_line1': '12 Marsh Lane',
    'address_line2': '',
    'city': 'Bristol',
    'state': '',
    'postal_code': 'BS1 4DJ',
    'country': 'GB',
    'phone': '+44 117 496 0000',
}


class FakeCJ:
    """Routes CJ calls by path; records what was sent."""

    def __init__(self):
        self.calls: list[tuple[str, str, dict | None, dict | None]] = []
        self.routes: dict[tuple[str, str], object] = {
            ('POST', '/authentication/getAccessToken'): {
                'code': 200,
                'result': True,
                'data': {'openId': 4242, 'accessToken': 'tok-1', 'refreshToken': 'r-1'},
            },
        }

    def ok(self, method: str, path: str, data):
        self.routes[(method, path)] = {
            'code': 200,
            'result': True,
            'message': 'Success',
            'data': data,
        }

    def error(self, method: str, path: str, code: int, message: str, status: int = 200):
        self.routes[(method, path)] = (
            {'code': code, 'result': False, 'message': message, 'data': None},
            status,
        )

    def _respond(self, method, url, params=None, json_body=None):
        path = url.split('/api2.0/v1', 1)[1]
        self.calls.append((method, path, params, json_body))
        route = self.routes.get((method, path))
        if route is None:
            return _Resp({'code': 1600101, 'result': False, 'message': 'interface not found'}, 404)
        if callable(route):
            route = route(params, json_body)
        body, status = route if isinstance(route, tuple) else (route, 200)
        return _Resp(body, status)

    def request(self, method, url, params=None, json=None, headers=None, timeout=None):  # noqa: A002
        return self._respond(method, url, params, json)

    def post(self, url, json=None, headers=None, timeout=None):  # noqa: A002
        return self._respond('POST', url, None, json)

    def bodies(self, method: str, path: str) -> list:
        return [
            body if body is not None else params
            for m, p, params, body in self.calls
            if m == method and p == path
        ]


class _Resp:
    def __init__(self, body, status):
        self._body, self.status_code = body, status

    def json(self):
        return self._body


class CJTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        from plugins.registry import app_registry

        self.plugin = app_registry.get('cjdropshipping')
        self.addCleanup(self.plugin.set_config, 'api_key', '')
        self.plugin.set_config('api_key', 'CJ123@api@secret')
        for key in ('auto_pay', 'logistic_name', 'auto_forward', 'price_markup', 'charm_pricing'):
            self.addCleanup(self.plugin.set_config, key, self.plugin.get_config_value(key, None))
        self.fake = FakeCJ()
        patches = [
            mock.patch('requests.request', side_effect=self.fake.request),
            mock.patch('requests.post', side_effect=self.fake.post),
            mock.patch('plugins.installed.cjdropshipping.services.client._throttle'),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def product(self, slug='radio', vid='V-RADIO'):
        from plugins.installed.catalog.models import Product
        from plugins.installed.cjdropshipping.models import CJLink

        product = Product.objects.create(
            name='Wind-up radio',
            slug=slug,
            sku=slug.upper(),
            price=Money(Decimal('29.00'), 'USD'),
            status='active',
        )
        CJLink.objects.create(product=product, variant=None, cj_variant_id=vid, cj_product_id='P-1')
        return product

    def paid_order(self, product, qty=2):
        from plugins.installed.orders.models import Order, OrderItem

        order = Order.objects.create(
            email='ada@example.com',
            subtotal=Money(Decimal('58.00'), 'USD'),
            total=Money(Decimal('58.00'), 'USD'),
            payment_status='paid',
            shipping_address=dict(ADDRESS),
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            sku=product.sku,
            quantity=qty,
            unit_price=Money(Decimal('29.00'), 'USD'),
            total_price=Money(Decimal('58.00'), 'USD'),
        )
        Order.objects.filter(pk=order.pk).update(status='confirmed')
        return Order.objects.get(pk=order.pk)


class ClientTests(CJTestCase):
    def test_success_is_http_200_and_code_200(self):
        from plugins.installed.cjdropshipping.services.client import request

        self.fake.ok('GET', '/setting/get', {'openName': 'Irving'})
        self.assertEqual(request('GET', '/setting/get'), {'openName': 'Irving'})
        sent = [c for c in self.fake.calls if c[1] == '/authentication/getAccessToken']
        self.assertEqual(sent[0][3], {'apiKey': 'CJ123@api@secret'})

    def test_a_failure_code_raises_with_the_code(self):
        from plugins.installed.cjdropshipping.services.client import CJError, request

        self.fake.error('GET', '/shopping/pay/getBalance', 1600200, 'Too much request')
        with self.assertRaises(CJError) as ctx:
            request('GET', '/shopping/pay/getBalance')
        self.assertEqual(ctx.exception.code, 1600200)

    def test_a_rejected_token_is_fetched_again_once(self):
        from plugins.installed.cjdropshipping.services.client import request

        attempts = {'n': 0}

        def flaky(params, body):
            attempts['n'] += 1
            if attempts['n'] == 1:
                return {'code': 1600001, 'result': False, 'message': 'Authentication failed'}, 401
            return {'code': 200, 'result': True, 'data': {'amount': 10}}

        self.fake.routes[('GET', '/shopping/pay/getBalance')] = flaky
        self.assertEqual(request('GET', '/shopping/pay/getBalance'), {'amount': 10})
        token_calls = [c for c in self.fake.calls if c[1] == '/authentication/getAccessToken']
        self.assertEqual(len(token_calls), 2)


class WebhookSignatureTests(TestCase):
    def test_the_docs_test_vector(self):
        from plugins.installed.cjdropshipping.services.webhooks import signature, verify

        body = b'{"messageId":"123111","messageType":"INSERT","params":"123","type":"PRODUCT"}'
        self.assertEqual(signature(body, '123'), 'AHxoGFMoS/4mZfJ5vFes5//Pz2QibFQhh3GlrTtnWpk=')
        self.assertTrue(verify(body, 'AHxoGFMoS/4mZfJ5vFes5//Pz2QibFQhh3GlrTtnWpk=', '123'))
        self.assertFalse(verify(body, 'nope', '123'))
        self.assertFalse(verify(body, 'AHxoGFMoS/4mZfJ5vFes5//Pz2QibFQhh3GlrTtnWpk=', ''))


class ImportTests(CJTestCase):
    def test_search_reads_the_nested_product_lists(self):
        from plugins.installed.cjdropshipping.services.catalog import search

        self.fake.ok(
            'GET',
            '/product/listV2',
            {
                'totalRecords': 1,
                'content': [
                    {
                        'productList': [
                            {
                                'id': 'P-9',
                                'nameEn': 'Solar panel',
                                'sku': 'CJSP1',
                                'bigImage': 'https://cf.cj/x.jpg',
                                'sellPrice': '12.50-14.00',
                                'warehouseInventoryNum': 30,
                            }
                        ]
                    }
                ],
            },
        )
        result = search('solar')
        self.assertEqual(result['items'][0]['pid'], 'P-9')
        self.assertEqual(result['items'][0]['price'], Decimal('12.50'))
        self.assertEqual(self.fake.bodies('GET', '/product/listV2')[0]['keyWord'], 'solar')

    def test_import_makes_a_linked_draft_with_marked_up_prices(self):
        from plugins.installed.catalog.models import Product
        from plugins.installed.cjdropshipping.models import CJLink
        from plugins.installed.cjdropshipping.services.catalog import import_cj_product

        self.plugin.set_config('price_markup', 2.5)
        self.plugin.set_config('charm_pricing', True)
        self.fake.ok(
            'GET',
            '/product/query',
            {
                'pid': 'P-7',
                'productNameEn': 'Emergency LED lantern',
                'sellPrice': '6.00',
                'description': '<p>Bright.</p><script>alert(1)</script><img src="x">',
                'productImageSet': ['https://cf.cj/a.jpg', 'https://cf.cj/b.jpg'],
                'variants': [
                    {
                        'vid': 'V-A',
                        'variantNameEn': 'Lantern Black',
                        'variantSku': 'CJL-B',
                        'variantSellPrice': 6.0,
                    },
                    {
                        'vid': 'V-B',
                        'variantNameEn': 'Lantern White',
                        'variantSku': 'CJL-W',
                        'variantSellPrice': 7.2,
                    },
                ],
            },
        )
        self.fake.ok('POST', '/webhook/product/subscribe', {'successProductIds': ['P-7']})
        with mock.patch('plugins.installed.catalog.services.images.add_product_image') as add_image:
            result = import_cj_product('P-7')
        product = Product.objects.get(pk=result.product.pk)
        self.assertEqual(product.status, 'draft')
        self.assertEqual(product.product_type, 'variable')
        self.assertNotIn('script', product.description)
        self.assertNotIn('<img', product.description)
        links = {link.cj_variant_id: link for link in CJLink.objects.filter(product=product)}
        self.assertEqual(set(links), {'V-A', 'V-B'})
        self.assertEqual(
            links['V-B'].variant.price.amount, Decimal('17.99')
        )  # 7.20 × 2.5 = 18.00 → 17.99
        self.assertEqual(add_image.call_count, 2)
        self.assertTrue(add_image.call_args_list[0].kwargs['is_primary'])
        self.assertEqual(
            self.fake.bodies('POST', '/webhook/product/subscribe'), [{'productIds': ['P-7']}]
        )


class OrderTests(CJTestCase):
    def setUp(self):
        super().setUp()
        self.plugin.set_config('logistic_name', 'CJPacket Ordinary')
        self.plugin.set_config('auto_pay', False)

    def _created(self, status='CREATED'):
        self.fake.ok(
            'POST',
            '/shopping/order/createOrderV2',
            {
                'orderId': 'CJ-100',
                'orderNumber': 'x',
                'orderStatus': status,
                'actualPayment': 11.40,
                'interceptOrderReasons': [],
            },
        )

    def test_a_paid_order_becomes_a_cj_order_with_the_right_body(self):
        from plugins.installed.cjdropshipping.services.orders import forward_order

        self._created()
        order = self.paid_order(self.product())
        record = forward_order(order)
        self.assertEqual(record.status, 'created')
        self.assertEqual(record.cj_order_id, 'CJ-100')
        body = self.fake.bodies('POST', '/shopping/order/createOrderV2')[0]
        self.assertEqual(body['orderNumber'], order.order_number)
        self.assertEqual(body['shippingCountryCode'], 'GB')
        self.assertEqual(body['shippingCountry'], 'United Kingdom')
        self.assertEqual(body['shippingProvince'], 'Bristol')  # no county given: the city stands in
        self.assertEqual(body['logisticName'], 'CJPacket Ordinary')
        self.assertEqual(body['fromCountryCode'], 'CN')
        self.assertEqual(body['payType'], 3)
        self.assertEqual(
            body['products'],
            [{'vid': 'V-RADIO', 'quantity': 2, 'storeLineItemId': str(order.items.get().pk)}],
        )
        from plugins.installed.orders.models import Order

        self.assertEqual(Order.objects.get(pk=order.pk).status, 'processing')

    def test_sending_twice_sends_once(self):
        from plugins.installed.cjdropshipping.services.orders import forward_order

        self._created()
        order = self.paid_order(self.product())
        forward_order(order)
        self.assertIsNone(forward_order(order))
        self.assertEqual(len(self.fake.bodies('POST', '/shopping/order/createOrderV2')), 1)

    def test_auto_pay_uses_pay_type_2(self):
        from plugins.installed.cjdropshipping.services.orders import forward_order

        self.plugin.set_config('auto_pay', True)
        self._created(status='UNSHIPPED')
        record = forward_order(self.paid_order(self.product()))
        self.assertEqual(self.fake.bodies('POST', '/shopping/order/createOrderV2')[0]['payType'], 2)
        self.assertEqual(record.status, 'paid')

    def test_cheapest_method_when_none_is_set(self):
        from plugins.installed.cjdropshipping.services.orders import forward_order

        self.plugin.set_config('logistic_name', '')
        self.fake.ok(
            'POST',
            '/logistic/freightCalculate',
            [
                {'logisticName': 'DHL', 'logisticPrice': 30.0, 'logisticAging': '3-5'},
                {
                    'logisticName': 'CJPacket Ordinary',
                    'logisticPrice': 4.1,
                    'logisticAging': '10-20',
                },
            ],
        )
        self._created()
        forward_order(self.paid_order(self.product()))
        self.assertEqual(
            self.fake.bodies('POST', '/shopping/order/createOrderV2')[0]['logisticName'],
            'CJPacket Ordinary',
        )
        freight = self.fake.bodies('POST', '/logistic/freightCalculate')[0]
        self.assertEqual(freight['endCountryCode'], 'GB')
        self.assertEqual(freight['products'], [{'quantity': 2, 'vid': 'V-RADIO'}])

    def test_a_refused_order_is_recorded_and_can_be_retried(self):
        from plugins.installed.cjdropshipping.services.orders import forward_order

        self.fake.error('POST', '/shopping/order/createOrderV2', 1605001, 'Logistic invalid')
        order = self.paid_order(self.product())
        record = forward_order(order)
        self.assertEqual(record.status, 'failed')
        self.assertIn('1605001', record.note)
        self._created()
        self.assertEqual(forward_order(order).status, 'created')

    def test_an_order_cj_already_has_is_adopted(self):
        from plugins.installed.cjdropshipping.services.orders import forward_order

        self.fake.error('POST', '/shopping/order/createOrderV2', 1603003, 'Order exist')
        self.fake.ok(
            'GET',
            '/shopping/order/getOrderDetail',
            {'orderId': 'CJ-77', 'orderStatus': 'UNSHIPPED'},
        )
        record = forward_order(self.paid_order(self.product()))
        self.assertEqual((record.cj_order_id, record.status), ('CJ-77', 'paid'))

    def test_paying_confirms_then_pays_from_the_balance(self):
        from plugins.installed.cjdropshipping.services.orders import forward_order, pay

        self._created()
        record = forward_order(self.paid_order(self.product()))
        self.fake.ok('PATCH', '/shopping/order/confirmOrder', 'CJ-100')
        self.fake.ok('POST', '/shopping/pay/payBalance', None)
        self.assertEqual(pay(record), '')
        self.assertEqual(record.status, 'paid')
        self.assertEqual(
            self.fake.bodies('POST', '/shopping/pay/payBalance'), [{'orderId': 'CJ-100'}]
        )

    def test_an_empty_balance_is_reported_not_raised(self):
        from plugins.installed.cjdropshipping.services.orders import forward_order, pay

        self._created()
        record = forward_order(self.paid_order(self.product()))
        self.fake.ok('PATCH', '/shopping/order/confirmOrder', 'CJ-100')
        self.fake.error('POST', '/shopping/pay/payBalance', 1604000, 'Balance is insufficient')
        self.assertEqual(pay(record), 'Balance is insufficient')
        self.assertEqual(record.status, 'created')

    def test_the_sweep_ships_the_order_with_cj_tracking(self):
        from plugins.installed.cjdropshipping.services.orders import forward_order, sync_open_orders
        from plugins.installed.orders.models import Fulfillment, Order

        self._created(status='UNSHIPPED')
        order = self.paid_order(self.product())
        forward_order(order)
        self.fake.ok(
            'POST',
            '/shopping/order/getOrderDetailBatch',
            [
                {
                    'orderId': 'CJ-100',
                    'orderStatus': 'SHIPPED',
                    'trackNumber': 'YT123',
                    'trackingProvider': 'Yun Express',
                    'trackingUrl': '',
                }
            ],
        )
        self.assertEqual(sync_open_orders(), 1)
        order = Order.objects.get(pk=order.pk)
        self.assertEqual(order.status, 'shipped')
        fulfillment = Fulfillment.objects.get(order=order)
        self.assertEqual(
            (fulfillment.tracking_number, fulfillment.carrier), ('YT123', 'Yun Express')
        )
        self.assertIn('YT123', fulfillment.tracking_url)

    def test_paid_hook_sends_the_order(self):
        from morpheus.core import MorpheusEvents, hook_registry
        from plugins.installed.cjdropshipping.models import CJOrder

        self.plugin.set_config('auto_forward', True)
        self._created()
        order = self.paid_order(self.product())
        hook_registry.fire(MorpheusEvents.ORDER_PAID, order=order)
        self.assertEqual(CJOrder.objects.get(order=order).cj_order_id, 'CJ-100')

    def test_an_order_cancelled_in_the_store_is_deleted_at_cj(self):
        from morpheus.core import MorpheusEvents, hook_registry
        from plugins.installed.cjdropshipping.models import CJOrder
        from plugins.installed.cjdropshipping.services.orders import forward_order

        self._created()
        order = self.paid_order(self.product())
        forward_order(order)
        self.fake.ok('DELETE', '/shopping/order/deleteOrder', 'CJ-100')
        hook_registry.fire(MorpheusEvents.ORDER_CANCELLED, order=order)
        record = CJOrder.objects.get(order=order)
        self.assertEqual(record.status, 'cancelled')
        self.assertEqual(
            self.fake.bodies('DELETE', '/shopping/order/deleteOrder'), [{'orderId': 'CJ-100'}]
        )


class WebhookViewTests(CJTestCase):
    def _post(self, payload: dict, *, sign: str | None = None):
        from plugins.installed.cjdropshipping.services.webhooks import signature

        body = json.dumps(payload, separators=(',', ':')).encode()
        header = signature(body, '4242') if sign is None else sign
        return Client().post(
            '/cj/webhook/', body, content_type='application/json', HTTP_SIGN=header
        )

    def _sent_order(self):
        from plugins.installed.cjdropshipping.services.orders import forward_order

        self.plugin.set_config('logistic_name', 'CJPacket Ordinary')
        self.fake.ok(
            'POST', '/shopping/order/createOrderV2', {'orderId': 'CJ-5', 'orderStatus': 'UNSHIPPED'}
        )
        order = self.paid_order(self.product())
        forward_order(order)
        return order

    def test_a_signed_logistic_message_ships_the_order(self):
        from plugins.installed.orders.models import Order

        order = self._sent_order()
        message = {
            'messageId': 'm-1',
            'type': 'LOGISTIC',
            'messageType': 'UPDATE',
            'params': {
                'orderId': 'CJ-5',
                'storeOrderNumbers': [order.order_number],
                'logisticName': 'CJPacket Ordinary',
                'trackingNumber': 'CJP999',
                'trackingProvider': 'Royal Mail',
                'trackingStatus': 6,
            },
        }
        response = self._post(message)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.get(pk=order.pk).status, 'shipped')

    def test_an_unsigned_message_is_answered_and_ignored(self):
        from plugins.installed.orders.models import Order

        order = self._sent_order()
        message = {
            'messageId': 'm-2',
            'type': 'LOGISTIC',
            'params': {'orderId': 'CJ-5', 'trackingNumber': 'FAKE'},
        }
        response = self._post(message, sign='forged')
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(Order.objects.get(pk=order.pk).status, 'shipped')

    def test_stock_and_price_messages_update_the_link(self):
        from plugins.installed.cjdropshipping.models import CJLink

        self.product(vid='V-77')
        self._post(
            {
                'messageId': 'm-3',
                'type': 'STOCK',
                'messageType': 'UPDATE',
                'params': {
                    'V-77': [{'vid': 'V-77', 'storageNum': 12}, {'vid': 'V-77', 'storageNum': 3}]
                },
            }
        )
        self._post(
            {
                'messageId': 'm-4',
                'type': 'VARIANT',
                'messageType': 'UPDATE',
                'params': {'vid': 'V-77', 'variantSellPrice': 8.25, 'fields': ['variantSellPrice']},
            }
        )
        link = CJLink.objects.get(cj_variant_id='V-77')
        self.assertEqual((link.stock, link.cost), (15, Decimal('8.25')))


class DashboardTests(CJTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(
            get_user_model().objects.create_user(
                username='o', email='o@x.test', password='x', is_staff=True, is_superuser=True
            )
        )

    def test_the_page_renders_with_search_results(self):
        self.fake.ok(
            'GET',
            '/product/listV2',
            {
                'totalRecords': 1,
                'content': [
                    {
                        'productList': [
                            {
                                'id': 'P-1',
                                'nameEn': 'Hand-crank torch',
                                'sku': 'CJT',
                                'sellPrice': '3.10',
                            }
                        ]
                    }
                ],
            },
        )
        response = self.client.get('/dashboard/apps/cjdropshipping/cj/?q=torch')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hand-crank torch')
        self.assertContains(response, '/cj/webhook/')

    def test_the_settings_keys_are_on_a_panel(self):
        from plugins.registry import app_registry

        panels = [
            e for e in app_registry.all_settings_panels() if str(e['plugin']) == 'cjdropshipping'
        ]
        self.assertEqual(len(panels), 1)
        props = panels[0]['panel'].schema['properties']
        self.assertEqual(props['api_key']['format'], 'password')


def _png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new('RGB', (40, 40), (10, 10, 10)).save(buf, 'PNG')
    return buf.getvalue()
