"""Server-side GA4 events belong to the shopper's own visit (v0.127.0).

Every Measurement Protocol hit used to carry a client_id the server made up on
the spot, so in GA4 each purchase, cart change and search was a new user with a
new session and no traffic source. The browser's IDs are now read from its GA
cookies, and the order keeps them for the payment webhook that confirms it.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from core.errors.context import current_request
from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Order
from plugins.installed.tracking.models import TrackingSettings
from plugins.installed.tracking.services.identity import ga_ids, user_id
from plugins.registry import app_registry

_DELAY = 'plugins.installed.tracking.tasks.send_event_task.delay'
_BROWSER = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15'
_GA = 'GA1.1.1234567890.1700000000'
_SESSION = 'GS2.1.s1761700000$o3$g1$t1761700100$j60$l0$h0'


def _store(**fields) -> TrackingSettings:
    from core.models import StoreSettings

    row = StoreSettings.objects.first() or StoreSettings()
    row.gdpr_enabled = False
    row.save()
    cache.delete('morph:gdpr_enabled')
    s = TrackingSettings.get_solo()
    s.measurement_id = 'G-TEST1234'
    s.api_secret = 'secret'
    s.client_side_enabled = False
    for key, value in fields.items():
        setattr(s, key, value)
    s.save()
    return s


class CookieTests(TestCase):
    def _req(self, **cookies):
        request = RequestFactory().get('/')
        request.COOKIES.update(cookies)
        return request

    def test_both_cookie_formats(self):
        self.assertEqual(
            ga_ids(self._req(_ga=_GA, _ga_TEST1234=_SESSION), 'G-TEST1234'),
            {'client_id': '1234567890.1700000000', 'session_id': '1761700000'},
        )
        old = self._req(_ga=_GA, _ga_TEST1234='GS1.1.1699999999.4.1.1700000100.0.0.0')
        self.assertEqual(ga_ids(old, 'G-TEST1234')['session_id'], '1699999999')

    def test_garbage_and_other_streams_give_nothing(self):
        self.assertEqual(ga_ids(self._req(_ga='nope', _ga_OTHER=_SESSION), 'G-TEST1234'), {})


class ProductViewTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Flint',
            slug='flint-probe',
            sku='FLINT',
            price=Money(Decimal('3'), 'USD'),
            product_type='simple',
            status='active',
        )

    def _view(self, **extra):
        with patch(_DELAY) as delay:
            self.client.get('/products/flint-probe/', HTTP_USER_AGENT=_BROWSER, **extra)
        return delay

    def test_the_hit_carries_the_browsers_ids(self):
        _store()
        self.client.cookies['_ga'] = _GA
        self.client.cookies['_ga_TEST1234'] = _SESSION
        kwargs = self._view().call_args.kwargs
        self.assertEqual(kwargs['client_id'], '1234567890.1700000000')
        self.assertEqual(kwargs['session_id'], '1761700000')
        # An unmanaged store: nothing restricts the ad signals.
        self.assertEqual(
            kwargs['consent'], {'ad_user_data': 'GRANTED', 'ad_personalization': 'GRANTED'}
        )

    def test_the_browser_tag_sends_it_instead(self):
        _store(client_side_enabled=True)
        self._view().assert_not_called()

    def test_nothing_is_queued_without_an_api_secret(self):
        _store(api_secret='')
        self._view().assert_not_called()

    def test_the_filters_apply(self):
        _store(bot_patterns=['Safari/605'])
        self._view().assert_not_called()
        _store(bot_patterns=[], block_paths=['/products/flint'])
        self._view().assert_not_called()


class PurchaseTests(TestCase):
    def setUp(self):
        self.customer = get_user_model().objects.create_user(username='c1', email='c1@example.com')
        self.order = Order.objects.create(
            email='c1@example.com',
            customer=self.customer,
            subtotal=Money(Decimal('10.00'), 'USD'),
            total=Money(Decimal('10.00'), 'USD'),
        )
        self.plugin = app_registry.get('tracking')

    def _place_in_checkout(self):
        request = RequestFactory().get('/checkout/')
        request.COOKIES.update({'_ga': _GA, '_ga_TEST1234': _SESSION})
        token = current_request.set(request)
        try:
            self.plugin.on_order_placed(order=self.order)
        finally:
            current_request.reset(token)

    def test_the_order_remembers_the_visit_and_the_webhook_uses_it(self):
        _store(user_id_enabled=True)
        self._place_in_checkout()
        # The status field is FSM-protected, so refresh_from_db() refuses: re-read it.
        self.order = Order.objects.get(pk=self.order.pk)
        self.assertEqual(self.order.metadata['ga']['client_id'], '1234567890.1700000000')
        # The payment webhook: no request, only the order.
        with patch(_DELAY) as delay:
            self.plugin.on_order_paid(order=self.order)
        kwargs = delay.call_args.kwargs
        self.assertEqual(kwargs['event_name'], 'purchase')
        self.assertEqual(kwargs['client_id'], '1234567890.1700000000')
        self.assertEqual(kwargs['session_id'], '1761700000')
        # The same hash the browser tag sends for this customer.
        self.assertEqual(kwargs['user_id'], user_id(self.customer.pk))

    def test_no_user_id_unless_switched_on(self):
        _store()
        with patch(_DELAY) as delay:
            self.plugin.on_order_paid(order=self.order)
        self.assertNotIn('user_id', delay.call_args.kwargs)

    def test_a_visit_without_ga_cookies_stamps_nothing(self):
        _store()
        token = current_request.set(RequestFactory().get('/checkout/'))
        try:
            self.plugin.on_order_placed(order=self.order)
        finally:
            current_request.reset(token)
        self.assertNotIn('ga', Order.objects.get(pk=self.order.pk).metadata or {})


class DebugModeTests(TestCase):
    def test_debug_mode_rides_on_the_event(self):
        # DebugView reads the event parameter; the query string sent until
        # v0.127.0 put nothing there.
        from plugins.installed.tracking.services import measurement_protocol

        _store(debug_mode=True)
        with patch.object(measurement_protocol._urlrequest, 'urlopen') as urlopen:
            urlopen.return_value.__enter__.return_value.status = 204
            urlopen.return_value.__enter__.return_value.read.return_value = b''
            row = measurement_protocol.send_event(event_name='search', params={'search_term': 'x'})
        self.assertTrue(row.payload['events'][0]['params']['debug_mode'])
        self.assertNotIn('debug_mode', urlopen.call_args.args[0].full_url)
