"""AliExpress: signing, OAuth, import, placing/paying/tracking orders, the pages.

AliExpress is faked at the HTTP layer (``requests.post``) with the response
shapes of the official docs — ``<method>_response`` envelopes, list wrappers,
``error_response`` — and the fake checks every request's signature with the
real algorithm, so a request the gateway would refuse fails here too.
"""

from __future__ import annotations

import json
import time
from datetime import timedelta
from decimal import Decimal
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase
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
SECRET = 's3cret'
DAY_MS = 24 * 60 * 60 * 1000
_CONFIG_KEYS = (
    'app_key',
    'app_secret',
    'ship_to_country',
    'logistics_service',
    'auto_forward',
    'auto_pay',
    'price_markup',
    'charm_pricing',
    'mark_processing_when_sent',
    '_access_token',
    '_refresh_token',
    '_access_expires_ms',
    '_refresh_expires_ms',
    '_account',
)


def _now_ms() -> int:
    return int(time.time() * 1000)


class _Resp:
    def __init__(self, body, status=200):
        self._body, self.status_code = body, status

    def json(self):
        return self._body


class _Raw:
    """A route answered exactly as given (no ``<method>_response`` envelope)."""

    def __init__(self, body):
        self.body = body


class FakeAE:
    """Routes AliExpress calls by method name (or system path); checks signatures."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.routes: dict[str, object] = {}

    def ok(self, target: str, body) -> None:
        self.routes[target] = body

    def error(self, target: str, sub_msg: str, sub_code: str = 'isv.error') -> None:
        self.routes[target] = _Raw(
            {
                'error_response': {
                    'type': 'ISV',
                    'code': 'IllegalParameter',
                    'msg': 'Illegal parameter',
                    'sub_code': sub_code,
                    'sub_msg': sub_msg,
                }
            }
        )

    def post(self, url, data=None, timeout=None):
        from plugins.installed.aliexpress.services.client import GATEWAY, sign

        data = dict(data or {})
        if url == f'{GATEWAY}/sync':
            target, api_path = data.get('method', ''), ''
        else:
            api_path = url.split('/rest', 1)[1]
            target = api_path
        unsigned = {k: v for k, v in data.items() if k != 'sign'}
        if data.get('sign') != sign(SECRET, unsigned, api_path):
            return _Resp({'error_response': {'code': 'IncompleteSignature', 'msg': 'bad sign'}})
        self.calls.append((target, data))
        route = self.routes.get(target)
        if route is None:
            return _Resp({'error_response': {'code': 'InvalidApiPath', 'msg': 'no such api'}})
        if callable(route):
            route = route(data)
        if isinstance(route, _Raw):
            return _Resp(route.body)
        if target.startswith('/'):
            return _Resp(route)
        return _Resp({f'{target.replace(".", "_")}_response': route})

    def sent(self, target: str) -> list[dict]:
        return [data for t, data in self.calls if t == target]

    def sent_json(self, target: str, name: str) -> list:
        return [json.loads(data[name]) for data in self.sent(target)]


def _product_detail(*, skus: int = 2) -> dict:
    all_skus = [
        {
            'sku_id': '120001',
            'sku_attr': '14:193#Black',
            'offer_sale_price': '6.00',
            'sku_available_stock': 40,
            'ae_sku_property_dtos': {
                'ae_sku_property_d_t_o': [
                    {
                        'sku_property_value': 'black',
                        'property_value_definition_name': 'Black',
                        'sku_image': 'https://ae01.alicdn.com/black.jpg',
                    }
                ]
            },
        },
        {
            'sku_id': '120002',
            'sku_attr': '14:175#White',
            'offer_sale_price': '7.20',
            'sku_available_stock': 0,
            'ae_sku_property_dtos': {'ae_sku_property_d_t_o': [{'sku_property_value': 'White'}]},
        },
    ][:skus]
    return {
        'result': {
            'ae_item_base_info_dto': {
                'product_id': 1005007,
                'subject': 'Emergency LED lantern',
                'detail': '<p>Bright.</p><script>alert(1)</script><img src="x">',
            },
            'ae_multimedia_info_dto': {
                'image_urls': 'https://ae01.alicdn.com/a.jpg;https://ae01.alicdn.com/b.jpg'
            },
            'ae_item_sku_info_dtos': {'ae_item_sku_info_d_t_o': all_skus},
        },
        'rsp_code': 200,
        'rsp_msg': 'Call succeeds',
    }


class AETestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        from plugins.registry import app_registry

        self.plugin = app_registry.get('aliexpress')
        for key in _CONFIG_KEYS:
            self.addCleanup(self.plugin.set_config, key, self.plugin.get_config_value(key, None))
        for key, value in {
            'app_key': '12345678',
            'app_secret': SECRET,
            'ship_to_country': 'US',
            'logistics_service': 'CAINIAO_STANDARD',
            'auto_pay': False,
            'auto_forward': True,
            'mark_processing_when_sent': True,
            '_access_token': 'tok-1',
            '_refresh_token': 'ref-1',
            '_access_expires_ms': _now_ms() + 20 * DAY_MS,
            '_refresh_expires_ms': _now_ms() + 50 * DAY_MS,
            '_account': 'buyer@example.com',
        }.items():
            self.plugin.set_config(key, value)
        self.fake = FakeAE()
        patcher = mock.patch('requests.post', side_effect=self.fake.post)
        patcher.start()
        self.addCleanup(patcher.stop)

    def product(self, slug='lantern', *, sku_attr='14:193#Black', sku_id='120001'):
        from plugins.installed.aliexpress.models import AELink
        from plugins.installed.catalog.models import Product

        product = Product.objects.create(
            name='Emergency LED lantern',
            slug=slug,
            sku=slug.upper(),
            price=Money(Decimal('29.00'), 'USD'),
            status='active',
        )
        AELink.objects.create(
            product=product,
            variant=None,
            ae_product_id='1005007',
            ae_sku_id=sku_id,
            sku_attr=sku_attr,
        )
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

    def placed(self, *ids: int) -> None:
        self.fake.ok(
            'aliexpress.ds.order.create',
            {'result': {'is_success': True, 'order_list': {'number': list(ids or (8101,))}}},
        )


class SignTests(SimpleTestCase):
    """The official vectors from the AliExpress Open Platform signature guide."""

    def test_the_business_method_vector(self):
        from plugins.installed.aliexpress.services.client import sign

        params = {
            'access_token': 'test',
            'aliexpress_category_id': '200135143',
            'app_key': '123456',
            'method': 'aliexpress.logistics.redefining.getonlinelogisticsinfo',
            'sign_method': 'sha256',
            'timestamp': '1517820392000',
        }
        self.assertEqual(
            sign('helloworld', params),
            'F7F7926B67316C9D1E8E15F7E66940ED3059B1638C497D77973F30046EFB5BBB',
        )

    def test_the_system_method_vector_puts_the_path_first(self):
        from plugins.installed.aliexpress.services.client import sign

        params = {
            'app_key': '12345678',
            'code': '3_500102_JxZ05Ux3cnnSSUm6dCxYg6Q26',
            'sign_method': 'sha256',
            'timestamp': '1517820392000',
        }
        self.assertEqual(
            sign('helloworld', params, '/auth/token/create'),
            '35607762342831B6A417A0DED84B79C05FEFBF116969C48AD6DC00279A9F4D81',
        )

    def test_empty_values_are_not_signed(self):
        from plugins.installed.aliexpress.services.client import sign

        base = {'app_key': '1', 'timestamp': '2'}
        self.assertEqual(sign('k', {**base, 'empty': ''}), sign('k', base))


class UnwrapTests(SimpleTestCase):
    def test_the_response_envelope_and_list_wrappers_go(self):
        from plugins.installed.aliexpress.services.client import unwrap

        raw = {
            'aliexpress_ds_order_create_response': {
                'result': {'is_success': True, 'order_list': {'number': [8101, 8102]}},
                'request_id': 'r1',
            }
        }
        self.assertEqual(
            unwrap(raw),
            {'result': {'is_success': True, 'order_list': [8101, 8102]}, 'request_id': 'r1'},
        )

    def test_a_result_or_data_list_keeps_its_name(self):
        from plugins.installed.aliexpress.services.client import unwrap

        self.assertEqual(unwrap({'result': [1, 2]}), {'result': [1, 2]})
        self.assertEqual(unwrap({'data': [3]}), {'data': [3]})


class ClientTests(AETestCase):
    def test_a_call_is_signed_and_carries_the_merchant_token(self):
        from plugins.installed.aliexpress.services.client import call

        self.fake.ok('aliexpress.ds.text.search', {'data': {'products': {}}})
        call('aliexpress.ds.text.search', {'keyWord': 'radio', 'skipped': ''})
        (sent,) = self.fake.sent('aliexpress.ds.text.search')
        self.assertEqual(sent['app_key'], '12345678')
        self.assertEqual(sent['sign_method'], 'sha256')
        self.assertEqual(sent['access_token'], 'tok-1')
        self.assertEqual(sent['format'], 'json')
        self.assertEqual(sent['keyWord'], 'radio')
        self.assertNotIn('skipped', sent)

    def test_an_error_response_raises_with_its_sub_code(self):
        from plugins.installed.aliexpress.services.client import AEError, call

        self.fake.error('aliexpress.ds.product.get', 'product not found', 'isv.product-not-exist')
        with self.assertRaises(AEError) as caught:
            call('aliexpress.ds.product.get', {'product_id': '1'})
        self.assertEqual(caught.exception.message, 'product not found')
        self.assertEqual(caught.exception.code, 'isv.product-not-exist')

    def test_the_token_is_refreshed_when_under_two_days_are_left(self):
        from plugins.installed.aliexpress.services.client import call, connection

        self.plugin.set_config('_access_expires_ms', _now_ms() + DAY_MS)
        self.fake.ok(
            '/auth/token/refresh',
            {
                'access_token': 'tok-2',
                'refresh_token': 'ref-2',
                'expire_time': _now_ms() + 30 * DAY_MS,
                'refresh_token_valid_time': _now_ms() + 60 * DAY_MS,
                'account': 'buyer@example.com',
                'code': '0',
            },
        )
        self.fake.ok('aliexpress.ds.text.search', {'data': {}})
        call('aliexpress.ds.text.search', {'keyWord': 'x'})
        self.assertEqual(self.fake.sent('/auth/token/refresh')[0]['refresh_token'], 'ref-1')
        self.assertEqual(self.fake.sent('aliexpress.ds.text.search')[0]['access_token'], 'tok-2')
        self.assertGreater(connection()['access_expires_ms'], _now_ms() + 29 * DAY_MS)

    def test_without_the_app_keys_nothing_is_sent(self):
        from plugins.installed.aliexpress.services.client import AEError, call

        self.plugin.set_config('app_secret', '')
        with self.assertRaises(AEError):
            call('aliexpress.ds.text.search', {'keyWord': 'x'})
        self.assertEqual(self.fake.calls, [])


class StaffClientMixin:
    def staff_client(self) -> Client:
        client = Client()
        client.force_login(
            get_user_model().objects.create_user(
                username='o', email='o@x.test', password='x', is_staff=True, is_superuser=True
            )
        )
        return client


class OAuthTests(StaffClientMixin, AETestCase):
    def setUp(self):
        super().setUp()
        from plugins.installed.aliexpress.services.client import disconnect

        disconnect()
        self.client = self.staff_client()

    def _start(self) -> dict:
        response = self.client.get('/dashboard/aliexpress/oauth/start/')
        self.assertEqual(response.status_code, 302)
        parts = urlsplit(response['Location'])
        self.assertEqual(
            f'{parts.scheme}://{parts.netloc}{parts.path}',
            'https://api-sg.aliexpress.com/oauth/authorize',
        )
        return {k: v[0] for k, v in parse_qs(parts.query).items()}

    def test_start_sends_the_merchant_to_aliexpress_with_a_state(self):
        query = self._start()
        self.assertEqual(query['client_id'], '12345678')
        self.assertEqual(query['response_type'], 'code')
        self.assertEqual(
            query['redirect_uri'], 'http://testserver/dashboard/aliexpress/oauth/callback/'
        )
        self.assertEqual(query['state'], self.client.session['aliexpress_oauth_state'])

    def test_a_callback_with_another_state_is_refused(self):
        from plugins.installed.aliexpress.services.client import connection

        self._start()
        response = self.client.get(
            '/dashboard/aliexpress/oauth/callback/', {'state': 'forged', 'code': 'c'}
        )
        self.assertRedirects(
            response, '/dashboard/apps/aliexpress/orders/', fetch_redirect_response=False
        )
        self.assertEqual(self.fake.calls, [])
        self.assertFalse(connection()['connected'])

    def test_the_callback_exchanges_the_code_and_stores_the_tokens(self):
        from plugins.installed.aliexpress.services.client import config, connection

        state = self._start()['state']
        self.fake.ok(
            '/auth/token/create',
            {
                'access_token': 'tok-new',
                'refresh_token': 'ref-new',
                'expire_time': _now_ms() + 30 * DAY_MS,
                'refresh_token_valid_time': _now_ms() + 60 * DAY_MS,
                'user_nick': 'prepper-buyer',
                'code': '0',
            },
        )
        response = self.client.get(
            '/dashboard/aliexpress/oauth/callback/', {'state': state, 'code': '3_500102_abc'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.fake.sent('/auth/token/create')[0]['code'], '3_500102_abc')
        self.assertEqual(connection()['account'], 'prepper-buyer')
        self.assertEqual(config()['_access_token'], 'tok-new')
        self.assertNotIn('aliexpress_oauth_state', self.client.session)

    def test_disconnect_forgets_the_tokens(self):
        from plugins.installed.aliexpress.services.client import connection

        self.plugin.set_config('_access_token', 'tok-1')
        response = self.client.post('/dashboard/aliexpress/oauth/disconnect/')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(connection()['connected'])


class ImportTests(AETestCase):
    def test_search_reads_the_product_list(self):
        from plugins.installed.aliexpress.services.catalog import search

        self.plugin.set_config('ship_to_country', 'GB')
        self.fake.ok(
            'aliexpress.ds.text.search',
            {
                'data': {
                    'totalCount': 1,
                    'products': {
                        'selection_search_product': [
                            {
                                'itemId': '1005001',
                                'title': 'Folding solar panel',
                                'itemMainPic': 'https://ae01.alicdn.com/s.jpg',
                                'targetSalePrice': '12.50',
                                'targetOriginalPriceCurrency': 'USD',
                                'orders': '320',
                                'evaluateRate': '97.1%',
                            }
                        ]
                    },
                },
                'code': '00',
            },
        )
        result = search('solar')
        self.assertEqual(result['items'][0]['id'], '1005001')
        self.assertEqual(result['items'][0]['price'], Decimal('12.50'))
        self.assertEqual(result['items'][0]['url'], 'https://www.aliexpress.com/item/1005001.html')
        sent = self.fake.sent('aliexpress.ds.text.search')[0]
        self.assertEqual((sent['keyWord'], sent['countryCode']), ('solar', 'UK'))

    def test_import_makes_a_linked_draft_with_marked_up_prices(self):
        from plugins.installed.aliexpress.models import AELink
        from plugins.installed.aliexpress.services.catalog import import_ae_product
        from plugins.installed.catalog.models import Product

        self.plugin.set_config('price_markup', 2.5)
        self.plugin.set_config('charm_pricing', True)
        self.fake.ok('aliexpress.ds.product.get', _product_detail())
        with mock.patch('plugins.installed.catalog.services.images.add_product_image') as add_image:
            result = import_ae_product('1005007')
        product = Product.objects.get(pk=result.product.pk)
        self.assertEqual(product.status, 'draft')
        self.assertEqual(product.product_type, 'variable')
        self.assertNotIn('script', product.description)
        self.assertNotIn('<img', product.description)
        links = {link.ae_sku_id: link for link in AELink.objects.filter(product=product)}
        self.assertEqual(set(links), {'120001', '120002'})
        self.assertEqual(links['120001'].sku_attr, '14:193#Black')
        self.assertEqual(links['120001'].variant.name, 'Black')
        self.assertEqual(links['120002'].stock, 0)
        self.assertEqual(
            links['120002'].variant.price.amount, Decimal('17.99')
        )  # 7.20 × 2.5 = 18.00 → 17.99
        self.assertEqual(add_image.call_count, 3)  # two photos + the black SKU's own
        self.assertEqual(self.fake.sent('aliexpress.ds.product.get')[0]['product_id'], '1005007')

    def test_a_single_sku_product_stays_simple_and_orders_without_sku_attr(self):
        from plugins.installed.aliexpress.models import AELink
        from plugins.installed.aliexpress.services.catalog import import_ae_product

        self.fake.ok('aliexpress.ds.product.get', _product_detail(skus=1))
        with mock.patch('plugins.installed.catalog.services.images.add_product_image'):
            result = import_ae_product('1005007')
        self.assertEqual(result.product.product_type, 'simple')
        link = AELink.objects.get(product=result.product)
        self.assertIsNone(link.variant)
        self.assertEqual((link.sku_attr, link.ae_sku_id), ('', '120001'))


class OrderTests(AETestCase):
    def test_a_paid_order_is_placed_with_the_right_request(self):
        from plugins.installed.aliexpress.services.orders import forward_order
        from plugins.installed.orders.models import Order

        self.placed()
        order = self.paid_order(self.product())
        record = forward_order(order)
        self.assertEqual(record.status, 'placed')
        self.assertEqual(record.ae_order_ids, ['8101'])
        self.assertEqual(record.pay_by, record.sent_at + timedelta(days=1))
        self.assertEqual(Order.objects.get(pk=order.pk).status, 'processing')
        (sent,) = self.fake.sent('aliexpress.ds.order.create')
        self.assertNotIn('ds_extend_request', sent)
        request = json.loads(sent['param_place_order_request4_open_api_d_t_o'])
        self.assertEqual(request['out_order_id'], order.order_number)
        address = request['logistics_address']
        self.assertEqual(address['country'], 'UK')
        self.assertEqual((address['city'], address['province']), ('Bristol', 'Bristol'))
        self.assertEqual(address['address'], '12 Marsh Lane')
        self.assertEqual(address['zip'], 'BS1 4DJ')
        self.assertEqual(address['mobile_no'], '441174960000')
        self.assertEqual(address['full_name'], 'Ada Lovelace')
        self.assertEqual(
            request['product_items'],
            [
                {
                    'product_id': 1005007,
                    'product_count': 2,
                    'sku_attr': '14:193#Black',
                    'logistics_service_name': 'CAINIAO_STANDARD',
                }
            ],
        )

    def test_placing_twice_places_once(self):
        from plugins.installed.aliexpress.services.orders import forward_order

        self.placed()
        order = self.paid_order(self.product())
        forward_order(order)
        self.assertIsNone(forward_order(order))
        self.assertEqual(len(self.fake.sent('aliexpress.ds.order.create')), 1)

    def test_auto_pay_asks_aliexpress_to_pay_by_paypal(self):
        from plugins.installed.aliexpress.services.orders import forward_order

        self.plugin.set_config('auto_pay', True)
        self.placed()
        forward_order(self.paid_order(self.product()))
        self.assertEqual(
            self.fake.sent_json('aliexpress.ds.order.create', 'ds_extend_request'),
            [{'payment': {'pay_currency': 'USD', 'try_to_pay': 'true'}}],
        )

    def test_the_cheapest_delivery_when_none_is_chosen(self):
        from plugins.installed.aliexpress.services.orders import forward_order

        self.plugin.set_config('logistics_service', '')
        self.fake.ok(
            'aliexpress.ds.freight.query',
            {
                'result': {
                    'success': True,
                    'delivery_options': {
                        'delivery_option_d_t_o': [
                            {
                                'code': 'EMS',
                                'company': 'EMS',
                                'shipping_fee_cent': '15.00',
                                'free_shipping': False,
                                'min_delivery_days': 5,
                                'max_delivery_days': 9,
                            },
                            {
                                'code': 'CAINIAO_FULFILLMENT_STD',
                                'company': 'AliExpress Standard Shipping',
                                'free_shipping': True,
                                'min_delivery_days': 10,
                                'max_delivery_days': 20,
                            },
                        ]
                    },
                }
            },
        )
        self.placed()
        forward_order(self.paid_order(self.product()))
        (query,) = self.fake.sent_json('aliexpress.ds.freight.query', 'queryDeliveryReq')
        self.assertEqual(
            (query['shipToCountry'], query['productId'], query['selectedSkuId'], query['quantity']),
            ('UK', '1005007', '120001', 2),
        )
        request = self.fake.sent_json(
            'aliexpress.ds.order.create', 'param_place_order_request4_open_api_d_t_o'
        )[0]
        self.assertEqual(
            request['product_items'][0]['logistics_service_name'], 'CAINIAO_FULFILLMENT_STD'
        )

    def test_a_refused_order_is_recorded_and_can_be_tried_again(self):
        from plugins.installed.aliexpress.services.orders import forward_order

        self.fake.ok(
            'aliexpress.ds.order.create',
            {
                'result': {
                    'is_success': False,
                    'error_code': 'B_DROPSHIPPER_DELIVERY_ADDRESS_VALIDATE_FAIL',
                    'error_msg': 'The delivery address is invalid',
                }
            },
        )
        order = self.paid_order(self.product())
        record = forward_order(order)
        self.assertEqual(record.status, 'failed')
        self.assertIn('The delivery address is invalid', record.note)
        self.assertIn('B_DROPSHIPPER_DELIVERY_ADDRESS_VALIDATE_FAIL', record.note)
        self.placed()
        self.assertEqual(forward_order(order).status, 'placed')

    def test_a_gateway_error_is_recorded(self):
        from plugins.installed.aliexpress.services.orders import forward_order

        self.fake.error('aliexpress.ds.order.create', 'Product is not available')
        record = forward_order(self.paid_order(self.product()))
        self.assertEqual((record.status, record.note), ('failed', 'Product is not available'))

    def test_the_payment_deadline_comes_from_aliexpress(self):
        from plugins.installed.aliexpress.services.orders import forward_order, sync_open_orders

        self.placed()
        record = forward_order(self.paid_order(self.product()))
        self.fake.ok(
            'aliexpress.trade.ds.order.get',
            {'result': {'order_status': 'PLACE_ORDER_SUCCESS', 'pay_timeout_second': 7200}},
        )
        self.assertEqual(sync_open_orders(), 1)
        record.refresh_from_db()
        self.assertEqual(record.status, 'placed')
        self.assertEqual(record.pay_by, record.sent_at + timedelta(seconds=7200))
        self.assertEqual(
            self.fake.sent_json('aliexpress.trade.ds.order.get', 'single_order_query'),
            [{'order_id': 8101}],
        )

    def test_the_order_ships_once_every_aliexpress_order_has_tracking(self):
        from plugins.installed.aliexpress.services.orders import forward_order, sync_open_orders
        from plugins.installed.orders.models import Fulfillment, Order

        self.placed(8101, 8102)
        order = self.paid_order(self.product())
        record = forward_order(order)
        self.fake.ok(
            'aliexpress.trade.ds.order.get', {'result': {'order_status': 'WAIT_SELLER_SEND_GOODS'}}
        )
        tracked = {'8101': 'LP001'}

        def tracking(data):
            number = tracked.get(data['ae_order_id'])
            lines = [{'mail_no': number, 'carrier_name': 'Cainiao'}] if number else []
            return {
                'result': {
                    'ret': True,
                    'data': {'tracking_detail_line_list': {'tracking_detail': lines}},
                }
            }

        self.fake.ok('aliexpress.ds.order.tracking.get', tracking)
        sync_open_orders()
        record.refresh_from_db()
        self.assertEqual(record.status, 'paid')
        self.assertEqual(set(record.tracking_numbers), {'8101'})
        self.assertEqual(Order.objects.get(pk=order.pk).status, 'processing')

        tracked['8102'] = 'LP002'
        sync_open_orders()
        record.refresh_from_db()
        self.assertEqual(record.status, 'shipped')
        self.assertEqual(Order.objects.get(pk=order.pk).status, 'shipped')
        fulfillment = Fulfillment.objects.get(order=order)
        self.assertEqual(
            (fulfillment.tracking_number, fulfillment.carrier), ('LP001, LP002', 'Cainiao')
        )
        self.assertIn('LP001', fulfillment.tracking_url)
        # 8101's number was kept from the first sweep, never asked for again
        asked = [d['ae_order_id'] for d in self.fake.sent('aliexpress.ds.order.tracking.get')]
        self.assertEqual(asked.count('8101'), 1)

    def test_the_paid_hook_places_the_order(self):
        from morpheus.core import MorpheusEvents, hook_registry
        from plugins.installed.aliexpress.models import AEOrder

        self.placed()
        order = self.paid_order(self.product())
        hook_registry.fire(MorpheusEvents.ORDER_PAID, order=order)
        self.assertEqual(AEOrder.objects.get(order=order).ae_order_ids, ['8101'])

    def test_a_store_cancellation_is_flagged_for_a_cancel_in_aliexpress(self):
        from morpheus.core import MorpheusEvents, hook_registry
        from plugins.installed.aliexpress.models import AEOrder
        from plugins.installed.aliexpress.services.orders import forward_order

        self.placed()
        order = self.paid_order(self.product())
        forward_order(order)
        calls_before = len(self.fake.calls)
        hook_registry.fire(MorpheusEvents.ORDER_CANCELLED, order=order)
        record = AEOrder.objects.get(order=order)
        self.assertEqual(record.status, 'cancelled')
        self.assertIn('8101', record.note)
        self.assertEqual(len(self.fake.calls), calls_before)  # there is no cancel method


class ProductCardTests(StaffClientMixin, AETestCase):
    def test_the_card_links_and_unlinks_a_product(self):
        from plugins.installed.aliexpress.models import AELink
        from plugins.installed.catalog.models import Product

        product = Product.objects.create(
            name='Water filter',
            slug='filter',
            sku='FILTER',
            price=Money(Decimal('19.00'), 'USD'),
            status='active',
        )
        self.plugin.on_product_form_saved(
            product=product,
            post={
                'ae_product__product': ' 1005009 ',
                'ae_sku_attr__product': '',
                'ae_sku_id__product': '130001',
            },
        )
        link = AELink.objects.get(product=product)
        self.assertEqual((link.ae_product_id, link.ae_sku_id), ('1005009', '130001'))
        self.plugin.on_product_form_saved(product=product, post={'name': 'Water filter'})
        self.assertTrue(AELink.objects.filter(product=product).exists())  # card not on the form
        self.plugin.on_product_form_saved(product=product, post={'ae_product__product': ''})
        self.assertFalse(AELink.objects.filter(product=product).exists())

    def test_the_card_renders_on_the_product_form(self):
        product = self.product()
        response = self.staff_client().get(f'/dashboard/products/{product.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-ae-card')
        self.assertContains(response, 'name="ae_product__product" value="1005007"')


class DashboardTests(StaffClientMixin, AETestCase):
    URL = '/dashboard/apps/aliexpress/orders/'

    def test_without_an_app_the_page_shows_the_setup_steps(self):
        self.plugin.set_config('app_key', '')
        response = self.staff_client().get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'openservice.aliexpress.com')
        self.assertContains(response, 'http://testserver/dashboard/aliexpress/oauth/callback/')

    def test_the_connected_page_searches_and_lists_orders_to_pay(self):
        from plugins.installed.aliexpress.services.orders import forward_order

        self.placed()
        order = self.paid_order(self.product())
        forward_order(order)
        self.fake.ok(
            'aliexpress.ds.text.search',
            {
                'data': {
                    'totalCount': 1,
                    'products': {
                        'selection_search_product': [
                            {'itemId': '1005003', 'title': 'Hand-crank torch', 'salePrice': '3.10'}
                        ]
                    },
                }
            },
        )
        response = self.staff_client().get(self.URL, {'q': 'torch'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hand-crank torch')
        self.assertContains(response, 'Connected')
        self.assertContains(response, 'Placed — pay these in AliExpress')
        self.assertContains(response, f'#{order.order_number}')
        self.assertContains(response, 'orderId=8101')

    def test_the_settings_keys_are_on_a_panel(self):
        from plugins.registry import app_registry

        panels = [e for e in app_registry.all_settings_panels() if str(e['plugin']) == 'aliexpress']
        self.assertEqual(len(panels), 1)
        props = panels[0]['panel'].schema['properties']
        self.assertEqual(props['app_secret']['format'], 'password')
        self.assertFalse(any(key.startswith('_') for key in props))  # tokens never on a form


class SweepTaskTests(AETestCase):
    def test_nothing_is_sent_until_the_account_is_connected(self):
        from plugins.installed.aliexpress.services.client import disconnect
        from plugins.installed.aliexpress.tasks import sync

        disconnect()
        self.assertEqual(sync(), {'skipped': 'not connected'})
        self.assertEqual(self.fake.calls, [])

    def test_the_sweep_places_missed_orders_and_reads_open_ones(self):
        from plugins.installed.aliexpress.models import AEOrder
        from plugins.installed.aliexpress.tasks import sync

        self.placed()
        self.fake.ok(
            'aliexpress.trade.ds.order.get', {'result': {'order_status': 'PLACE_ORDER_SUCCESS'}}
        )
        order = self.paid_order(self.product())
        self.assertEqual(sync(), {'placed': 1, 'read': 1})
        self.assertEqual(AEOrder.objects.get(order=order).status, 'placed')
