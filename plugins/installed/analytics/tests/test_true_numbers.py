"""What the Traffic page counts, checked against what happened.

The audit of 2026-11-12 found every pageview of an edge-cached page lost (the
server never saw it), a "session" that was a two-year cookie, every event without
consent counted as a session of its own, conversion able to pass 100 %, purchases
never tied to the visit that made them, add-to-cart counted only by the browser,
"today" ending at midnight UTC, and the referrer replaced by the store itself on
the reload after the cookie banner.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase
from django.utils import timezone
from djmoney.money import Money

from core.errors.context import current_request
from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.analytics import dashboard, services
from plugins.installed.analytics.models import AnalyticsEvent, AnalyticsSession, DailyMetric
from plugins.installed.orders.models import Order
from plugins.registry import app_registry

_BROWSER = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Version/17.5 Safari/605.1.15'
)
_SEMRUSH = 'Mozilla/5.0 (compatible; SemrushBot/7~bl; +http://www.semrush.com/bot.html)'
_CONSENT = '{"analytics": true, "functional": true, "marketing": true}'
_TRACK = '/api/analytics/track/'


def _config(**values):
    """Patch the analytics settings for one test."""
    return patch.object(services, '_config', return_value=values)


class PageHitTests(TestCase):
    """A pageview is the browser's own hit, so a page served from the edge cache counts."""

    def setUp(self):
        cache.clear()
        self.client = Client(HTTP_USER_AGENT=_BROWSER)

    def test_a_page_carries_one_hit_and_records_no_pageview_itself(self):
        body = self.client.get('/').content.decode()
        self.assertEqual(body.count('data-morph-hit'), 1)
        self.assertFalse(AnalyticsEvent.objects.filter(name='pageview').exists())

    def test_a_missing_page_a_crawler_and_a_json_fetch_get_no_hit(self):
        self.assertNotIn(b'data-morph-hit', self.client.get('/no-such-page-xyz/').content)
        self.assertNotIn(b'data-morph-hit', Client(HTTP_USER_AGENT=_SEMRUSH).get('/').content)
        self.assertNotIn(b'data-morph-hit', self.client.get('/csrf/').content)

    def test_a_switched_off_app_writes_no_script_and_sets_no_cookie(self):
        self.client.cookies['morpheus_consent'] = _CONSENT
        on = self.client.get('/')
        self.assertIn(b'data-morph-hit', on.content)
        self.assertIn('morph_aid', on.cookies)

        self.assertTrue(app_registry.is_active('analytics'))
        app_registry._active.discard('analytics')
        self.addCleanup(app_registry._active.add, 'analytics')
        cache.clear()
        client = Client(HTTP_USER_AGENT=_BROWSER)
        client.cookies['morpheus_consent'] = _CONSENT
        off = client.get('/')
        self.assertEqual(off.status_code, 200)
        self.assertNotIn(b'data-morph-hit', off.content)
        self.assertNotIn('morph_aid', off.cookies)

    def test_the_hit_is_a_pageview_and_only_a_pageview_is(self):
        self.client.post(
            _TRACK,
            data=json.dumps({'name': 'pageview', 'kind': 'pageview', 'url': 'https://x.test/'}),
            content_type='application/json',
        )
        self.client.post(
            _TRACK,
            data=json.dumps({'name': 'page.leave', 'kind': 'pageview'}),
            content_type='application/json',
        )
        self.assertEqual(AnalyticsEvent.objects.filter(kind='pageview').count(), 1)
        self.assertEqual(AnalyticsEvent.objects.get(name='page.leave').kind, 'custom')

    def test_a_crawler_that_runs_scripts_is_not_counted(self):
        Client(HTTP_USER_AGENT=_SEMRUSH).post(
            _TRACK, data=json.dumps({'name': 'pageview'}), content_type='application/json'
        )
        self.assertFalse(AnalyticsEvent.objects.exists())

    def test_the_first_hit_names_where_the_visitor_came_from(self):
        self.client.cookies['morpheus_consent'] = _CONSENT
        self.client.post(
            _TRACK,
            data=json.dumps(
                {
                    'name': 'pageview',
                    'url': 'https://x.test/products/?utm_source=chatgpt.com',
                    'referrer': '',
                }
            ),
            content_type='application/json',
        )
        session = AnalyticsSession.objects.get()
        self.assertEqual(session.utm_source, 'ai:chatgpt')
        self.assertEqual(session.utm_medium, 'ai-assistant')
        self.assertEqual(session.landing_url, '/products/')


class VisitsTests(TestCase):
    def _event(self, at, *, session=None, v=None, kind='pageview', name='pageview'):
        evt = AnalyticsEvent.objects.create(
            name=name, kind=kind, session=session, payload={'v': v} if v else {}
        )
        AnalyticsEvent.objects.filter(pk=evt.pk).update(created_at=at)

    def test_a_visit_ends_after_thirty_quiet_minutes(self):
        a = AnalyticsSession.objects.create(cookie_id='a')
        b = AnalyticsSession.objects.create(cookie_id='b')
        t0 = timezone.now().replace(hour=10, minute=0)
        self._event(t0, session=a)
        self._event(t0 + timedelta(minutes=20), session=a)
        self._event(t0 + timedelta(minutes=55), session=a)  # 35 quiet minutes: a new visit
        self._event(t0, session=b)
        self._event(t0, v='k1')  # cookieless visitor
        self._event(t0)  # nobody: no visit
        self.assertEqual(services.visits_and_visitors(AnalyticsEvent.objects.all()), (4, 3))

    def test_conversion_counts_only_purchases_by_counted_visitors(self):
        a = AnalyticsSession.objects.create(cookie_id='c')
        today = services.store_today()
        start, _ = services.day_bounds(today)
        at = start + timedelta(hours=1)
        self._event(at, session=a)
        self._event(at, session=a, kind='purchase', name='order.placed')
        self._event(at, kind='purchase', name='order.placed')  # no visitor behind it
        services.roll_daily(day=today)
        metric = {
            m.metric: m.value_int for m in DailyMetric.objects.filter(day=today, dimension='')
        }
        self.assertEqual(metric['sessions'], 1)
        self.assertEqual(metric['visitors'], 1)
        self.assertEqual(metric['orders'], 2)
        self.assertEqual(metric['counted_purchases'], 1)
        self.assertEqual(metric['conversion_rate'], 10_000)  # 100 %, never 200 %

    def test_a_ranked_row_that_fell_out_is_dropped_on_the_next_roll(self):
        today = services.store_today()
        start, _ = services.day_bounds(today)
        evt = AnalyticsEvent.objects.create(
            name='product.viewed', kind='product_view', product_slug='lamp'
        )
        AnalyticsEvent.objects.filter(pk=evt.pk).update(created_at=start + timedelta(hours=1))
        services.roll_daily(day=today)
        self.assertTrue(
            DailyMetric.objects.filter(metric='top_products', dimension='lamp').exists()
        )
        AnalyticsEvent.objects.all().delete()
        services.roll_daily(day=today)
        self.assertFalse(DailyMetric.objects.filter(metric='top_products').exists())


class StoreClockTests(TestCase):
    def test_a_day_is_the_stores_day(self):
        from core.models import StoreSettings

        StoreSettings.objects.create(timezone='Europe/Belgrade')
        start, end = services.day_bounds(datetime(2026, 11, 12).date())
        # Midnight in Belgrade is 23:00 UTC the evening before, in November.
        self.assertEqual(start.astimezone(UTC), datetime(2026, 11, 11, 23, 0, tzinfo=UTC))
        self.assertEqual(end - start, timedelta(days=1))

    def test_an_unknown_zone_falls_back_to_utc(self):
        from core.models import StoreSettings

        StoreSettings.objects.create(timezone='Mars/Olympus')
        start, _ = services.day_bounds(datetime(2026, 11, 12).date())
        self.assertEqual(start.utcoffset(), timedelta(0))


class DashboardWindowTests(TestCase):
    """The home tiles sum whole store days, and the comparison never shares one."""

    def _window(self, now, **query):
        from plugins.installed.admin_dashboard.views_split._shared import _resolve_date_range

        with patch('django.utils.timezone.now', return_value=now):
            date_range = _resolve_date_range(RequestFactory().get('/dashboard/', query))
            return date_range, dashboard._window(date_range)

    def test_last_7_days_is_seven_days_against_the_seven_before(self):
        now = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
        date_range, window = self._window(now, preset='7d')
        self.assertEqual(
            window,
            ((date(2026, 11, 6), date(2026, 11, 12)), (date(2026, 10, 30), date(2026, 11, 5))),
        )
        for offset in range(14):
            day = date(2026, 11, 12) - timedelta(days=offset)
            DailyMetric.objects.create(
                day=day, metric='sessions', value_int=100 if day == date(2026, 11, 5) else 1
            )
        with patch('django.utils.timezone.now', return_value=now):
            kpis = dashboard.on_dashboard_kpis([], date_range=date_range)
        visits = {k['label']: k for k in kpis}['Visits']
        self.assertEqual((visits['value'], visits['delta']), ('7', '-93%'))

    def test_today_and_a_custom_range_are_the_stores_days(self):
        from core.models import StoreSettings

        StoreSettings.objects.create(timezone='America/New_York')
        now = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)  # 10:00 in New York
        _, today = self._window(now, preset='today')
        self.assertEqual(
            today,
            ((date(2026, 11, 12), date(2026, 11, 12)), (date(2026, 11, 11), date(2026, 11, 11))),
        )
        _, custom = self._window(now, **{'from': '2026-11-01', 'to': '2026-11-03'})
        self.assertEqual(
            custom,
            ((date(2026, 11, 1), date(2026, 11, 3)), (date(2026, 10, 29), date(2026, 10, 31))),
        )


class CookielessTests(TestCase):
    def _request(self, user=None):
        request = RequestFactory().get('/', HTTP_USER_AGENT=_BROWSER, REMOTE_ADDR='203.0.113.9')
        if user is not None:
            request.user = user
        return request

    def test_off_by_default(self):
        evt = services.record_event(name='pageview', kind='pageview', request=self._request())
        self.assertNotIn('v', evt.payload)

    def test_on_a_visitor_without_consent_gets_the_days_key(self):
        cache.clear()
        with _config(cookieless_visits=True):
            first = services.record_event(name='pageview', kind='pageview', request=self._request())
            second = services.record_event(
                name='pageview', kind='pageview', request=self._request()
            )
        self.assertIsNone(first.session_id)
        self.assertEqual(len(first.payload['v']), 16)
        self.assertEqual(first.payload['v'], second.payload['v'])

    def test_never_beside_a_customer(self):
        from django.contrib.auth import get_user_model

        customer = get_user_model().objects.create_user(username='cl', password='x')
        with _config(cookieless_visits=True):
            evt = services.record_event(
                name='order.placed', kind='purchase', request=self._request(), customer=customer
            )
        self.assertNotIn('v', evt.payload)

    def test_a_guests_order_never_carries_the_key(self):
        # The order holds the guest's email and address: the day's key beside
        # it would name who browsed what. The visit and the purchase still count.
        cache.clear()
        order = Order.objects.create(
            email='guest@example.com',
            subtotal=Money(Decimal('9.00'), 'EUR'),
            total=Money(Decimal('9.00'), 'EUR'),
        )
        checkout = RequestFactory().post(
            '/checkout/', HTTP_USER_AGENT=_BROWSER, REMOTE_ADDR='203.0.113.9'
        )
        token = current_request.set(checkout)
        try:
            with _config(cookieless_visits=True):
                page = services.record_event(
                    name='pageview', kind='pageview', request=self._request()
                )
                hook_registry.fire(MorpheusEvents.ORDER_PLACED, order=order)
                refund = services.record_event(
                    name='refund.created', kind='refund', request=checkout
                )
        finally:
            current_request.reset(token)
        key = page.payload['v']
        purchase = AnalyticsEvent.objects.get(name='order.placed')
        self.assertEqual(purchase.payload['order'], str(order.pk))
        for evt in (purchase, refund):
            self.assertNotIn('v', evt.payload)
            self.assertNotIn(key, json.dumps(evt.payload))
        self.order = Order.objects.get(pk=order.pk)  # the status field refuses refresh_from_db
        self.assertNotIn(key, json.dumps(self.order.metadata or {}))

        today = services.store_today()
        services.roll_daily(day=today)
        metric = {
            m.metric: m.value_int for m in DailyMetric.objects.filter(day=today, dimension='')
        }
        self.assertEqual(metric['sessions'], 1)
        self.assertEqual(metric['counted_purchases'], 1)


class OrderVisitTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            email='ov@example.com',
            subtotal=Money(Decimal('12.00'), 'EUR'),
            total=Money(Decimal('12.00'), 'EUR'),
        )

    def _checkout_request(self, path='/checkout/'):
        request = RequestFactory().post(path, HTTP_USER_AGENT=_BROWSER)
        request.COOKIES['morpheus_consent'] = _CONSENT
        request.COOKIES['morph_aid'] = 'shopper-1'
        return request

    def _place(self, request):
        token = current_request.set(request)
        try:
            hook_registry.fire(MorpheusEvents.ORDER_PLACED, order=self.order)
        finally:
            current_request.reset(token)

    def test_the_purchase_belongs_to_the_visit_and_so_does_the_payment(self):
        self._place(self._checkout_request())
        purchase = AnalyticsEvent.objects.get(name='order.placed')
        self.assertIsNotNone(purchase.session_id)
        self.assertEqual(purchase.payload['order'], str(self.order.pk))
        self.order = Order.objects.get(pk=self.order.pk)  # the status field refuses refresh_from_db
        self.assertEqual(self.order.metadata['analytics'], {'visitor': str(purchase.session_id)})

        # The webhook's request is Stripe's; the payment is still the shopper's visit.
        hook_registry.fire(MorpheusEvents.PAYMENT_CAPTURED, order=self.order)
        captured = AnalyticsEvent.objects.get(name=MorpheusEvents.PAYMENT_CAPTURED)
        self.assertEqual(captured.session_id, purchase.session_id)

    def test_an_order_placed_from_the_dashboard_is_nobodys_visit(self):
        self._place(self._checkout_request('/dashboard/orders/new/'))
        self.assertIsNone(AnalyticsEvent.objects.get(name='order.placed').session_id)
        self.order = Order.objects.get(pk=self.order.pk)  # the status field refuses refresh_from_db
        self.assertNotIn('analytics', self.order.metadata or {})

    def test_other_keys_on_the_order_are_kept(self):
        Order.objects.filter(pk=self.order.pk).update(metadata={'ga': {'client_id': '1.2'}})
        self.order = Order.objects.get(pk=self.order.pk)  # the status field refuses refresh_from_db
        self._place(self._checkout_request())
        self.order = Order.objects.get(pk=self.order.pk)  # the status field refuses refresh_from_db
        self.assertEqual(self.order.metadata['ga'], {'client_id': '1.2'})
        self.assertIn('analytics', self.order.metadata)


class CartAddTests(TestCase):
    def _fire(self, ua):
        from plugins.installed.catalog.models import Product

        product = Product.objects.create(
            name='Lamp', slug='ca-lamp', sku='CA-1', price=Money(Decimal('5'), 'EUR')
        )
        request = RequestFactory().post('/cart/add/', HTTP_USER_AGENT=ua)
        hook_registry.fire(MorpheusEvents.ADD_TO_CART, request=request, product=product, quantity=1)

    def test_the_server_counts_an_add_to_cart(self):
        self._fire(_BROWSER)
        evt = AnalyticsEvent.objects.get(name='cart.add')
        self.assertEqual((evt.kind, evt.product_slug), ('cart', 'ca-lamp'))

    def test_a_crawler_adding_to_a_cart_is_not(self):
        self._fire(_SEMRUSH)
        self.assertFalse(AnalyticsEvent.objects.filter(name='cart.add').exists())


class VisitorRetentionTests(TestCase):
    def test_the_setting_decides_how_long_a_visitor_is_kept(self):
        from plugins.installed.analytics.tasks import trim_old_visitors_task

        old = AnalyticsSession.objects.create(cookie_id='old')
        recent = AnalyticsSession.objects.create(cookie_id='recent')
        AnalyticsSession.objects.filter(pk=old.pk).update(
            last_seen_at=timezone.now() - timedelta(days=100)
        )
        AnalyticsSession.objects.filter(pk=recent.pk).update(
            last_seen_at=timezone.now() - timedelta(days=20)
        )
        with _config(keep_visitor_days=60):
            self.assertEqual(trim_old_visitors_task(), 1)
        self.assertEqual(
            list(AnalyticsSession.objects.values_list('cookie_id', flat=True)), ['recent']
        )


class SearchCountTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(HTTP_USER_AGENT=_BROWSER)

    def test_a_search_counts_once_with_its_result_count(self):
        from plugins.installed.catalog.models import Product

        for i in range(61):  # two pages of 60
            Product.objects.create(
                name=f'Lantern {i}',
                slug=f'sc-lantern-{i}',
                sku=f'SC-{i}',
                price=Money(Decimal('5'), 'EUR'),
                status='active',
            )
        self.client.get('/products/', {'q': 'lantern'})
        self.client.get('/products/', {'q': 'lantern', 'page': '2'})
        (search,) = AnalyticsEvent.objects.filter(kind='search')
        self.assertEqual(search.search_query, 'lantern')
        self.assertEqual(search.payload['results'], 61)
