"""Where visits came from, each visit under its own first page (v0.158.0).

The audit of 2026-11-12 found a traffic source that belonged to the visitor,
not the visit: the two-year analytics cookie kept the first visit's referrer
and tags, so a visitor who first came from Facebook and came back from Google
read as Facebook for two years; untagged referrals (a search engine, a blog)
were not sources at all; and nothing listed the searches that found nothing.
"""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.analytics import services
from plugins.installed.analytics.models import (
    AnalyticsEvent,
    AnalyticsSession,
    AnalyticsVisit,
    DailyMetric,
)
from plugins.installed.analytics.sources import classify
from plugins.installed.analytics.visits import search_terms, sources_report
from plugins.installed.orders.models import Order, Refund

_BROWSER = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Version/17.5 Safari/605.1.15'
)
_CONSENT = '{"analytics": true, "functional": true, "marketing": true}'
_TRACK = '/api/analytics/track/'


def _arrival(referrer='', query='', host='shop.test'):
    got = classify(referrer, parse_qs(query), host)
    return (got.get('ch'), got.get('s')) if got else None


class ClassifyTests(TestCase):
    def test_each_channel(self):
        cases = {
            ('https://www.google.com/', ''): ('organic', 'google'),
            ('https://www.google.co.uk/search?q=a', ''): ('organic', 'google'),
            ('https://duckduckgo.com/', ''): ('organic', 'duckduckgo'),
            ('https://www.google.com/', 'gclid=1'): ('paid', 'google'),
            ('', 'utm_source=google&utm_medium=cpc'): ('paid', 'google'),
            ('', 'msclkid=1'): ('paid', 'bing'),
            # An ad's click id beside a bare source tag is still the ad (review of PR #154).
            ('https://www.google.com/', 'gclid=1&utm_source=google'): ('paid', 'google'),
            ('', 'msclkid=1&utm_source=bing'): ('paid', 'bing'),
            ('', 'ttclid=1&utm_source=tiktok'): ('paid', 'tiktok'),
            ('', 'gclid=1&utm_source=google&utm_medium=email'): ('email', 'google'),
            ('', 'fbclid=1&utm_source=facebook'): ('social', 'facebook'),
            ('https://l.facebook.com/', ''): ('social', 'facebook'),
            ('', 'fbclid=1'): ('social', 'facebook'),
            ('https://t.co/x', ''): ('social', 'x'),
            ('', 'utm_source=instagram'): ('social', 'instagram'),
            ('', 'utm_source=newsletter&utm_medium=email'): ('email', 'newsletter'),
            ('https://mail.google.com/', ''): ('email', 'gmail'),
            ('https://chatgpt.com/', ''): ('ai', 'chatgpt'),
            ('', 'utm_source=chatgpt.com'): ('ai', 'chatgpt'),
            ('https://someblog.example/post', ''): ('referral', 'someblog.example'),
            ('', 'utm_source=partner'): ('referral', 'partner'),
            ('', ''): ('direct', None),
        }
        for (referrer, query), want in cases.items():
            with self.subTest(referrer=referrer, query=query):
                self.assertEqual(_arrival(referrer, query), want)

    def test_the_store_itself_and_a_payment_page_name_no_arrival(self):
        self.assertIsNone(_arrival('https://www.shop.test/products/'))
        self.assertIsNone(_arrival('https://checkout.stripe.com/c/pay/x'))
        self.assertEqual(
            classify('', parse_qs('utm_source=google&utm_medium=cpc&utm_campaign=Spring'), '')['c'],
            'Spring',
        )


class BeaconArrivalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(HTTP_USER_AGENT=_BROWSER, HTTP_CF_IPCOUNTRY='RS')
        self.client.cookies['morpheus_consent'] = _CONSENT

    def _hit(self, url='/', referrer='', **extra):
        self.client.post(
            _TRACK,
            data=json.dumps({'name': 'pageview', 'url': url, 'referrer': referrer, **extra}),
            content_type='application/json',
        )
        return AnalyticsEvent.objects.filter(kind='pageview').order_by('-created_at').first()

    def test_a_page_names_where_a_visit_starting_on_it_came_from(self):
        hit = self._hit('/books/?utm_source=google&utm_medium=cpc', 'https://www.google.com/')
        self.assertEqual(
            hit.payload['arr'],
            {'ch': 'paid', 's': 'google', 'm': 'cpc', 'cc': 'RS', 'd': 'desktop'},
        )

    def test_a_beacon_cannot_write_the_servers_own_keys(self):
        hit = self._hit('/', '', v='forged', arr={'ch': 'paid'}, src='hook', order='x', results=0)
        self.assertNotIn('v', hit.payload)
        self.assertNotIn('order', hit.payload)
        self.assertNotIn('results', hit.payload)
        self.assertEqual(hit.payload['arr']['ch'], 'direct')


class ConsentReloadTests(TestCase):
    """The reload after "Accept" keeps where the visit came from (review of PR #154).

    The page the banner reloads takes the carried entry and clears its cookie,
    so the beacon that follows names the store's own page as its referrer.
    """

    _STORE = 'http://testserver/'
    _BLOG = 'https://someblog.example/post'

    def setUp(self):
        from core.models import StoreSettings

        cache.clear()
        row = StoreSettings.objects.first() or StoreSettings()
        row.gdpr_enabled = True
        row.save()
        cache.delete('morph:gdpr_enabled')
        self.client = Client(HTTP_USER_AGENT=_BROWSER)

    def _beacon(self, url, referrer):
        seen = set(AnalyticsEvent.objects.values_list('pk', flat=True))
        self.client.post(
            _TRACK,
            data=json.dumps({'name': 'pageview', 'url': url, 'referrer': referrer}),
            content_type='application/json',
        )
        return AnalyticsEvent.objects.exclude(pk__in=seen).get(kind='pageview')

    def test_the_reloaded_page_is_filed_under_the_site_that_sent_the_visitor(self):
        from core.consent import ENTRY_COOKIE

        self.client.get('/', HTTP_REFERER=self._BLOG)
        self.assertIsNone(self._beacon('/', self._BLOG).session_id)  # no consent, no visit
        self.client.post(
            '/consent/save/',
            {'accept_all': '1', 'entry_url': self._STORE, 'entry_referrer': self._BLOG},
            HTTP_REFERER=self._STORE,
        )
        page = self.client.get('/', HTTP_REFERER=self._STORE)
        self.assertEqual(page.cookies[ENTRY_COOKIE]['max-age'], 0)  # the page took the entry

        first = self._beacon('/', self._STORE)
        self.assertEqual(
            (first.payload['arr'].get('ch'), first.payload['arr'].get('s')),
            ('referral', 'someblog.example'),
        )
        self.assertNotIn('ch', self._beacon('/books/', self._STORE).payload['arr'])

    def test_a_returning_visitor_is_not_filed_under_an_old_referrer(self):
        session = AnalyticsSession.objects.create(
            cookie_id='returning', referrer='https://l.facebook.com/', is_consented=True
        )
        AnalyticsSession.objects.filter(pk=session.pk).update(
            first_seen_at=session.first_seen_at - timedelta(days=200)
        )
        self.client.cookies['morpheus_consent'] = _CONSENT
        self.client.cookies[services.COOKIE_NAME] = 'returning'
        hit = self._beacon('/', self._STORE)
        self.assertEqual(hit.session_id, session.pk)
        self.assertNotIn('ch', hit.payload['arr'])


def _event(at, *, session=None, kind='pageview', name=None, url='/', payload=None, query=''):
    evt = AnalyticsEvent.objects.create(
        name=name or kind,
        kind=kind,
        session=session,
        url=url,
        payload=payload or {},
        search_query=query,
    )
    AnalyticsEvent.objects.filter(pk=evt.pk).update(created_at=at)
    return evt


def _page(at, session, arr, url='/'):
    return _event(at, session=session, payload={'arr': arr}, url=url)


class VisitSourceTests(TestCase):
    def setUp(self):
        self.today = services.store_today()
        self.start, _ = services.day_bounds(self.today)
        self.visitor = AnalyticsSession.objects.create(cookie_id='returning', utm_source='facebook')

    def _rows(self, day=None):
        return list(AnalyticsVisit.objects.filter(day=day or self.today).order_by('started_at'))

    def test_a_returning_visitor_is_filed_under_each_visits_own_source(self):
        at = self.start + timedelta(hours=1)
        _page(at, self.visitor, {'ch': 'social', 's': 'facebook'}, '/a/')
        _page(at + timedelta(minutes=10), self.visitor, {}, '/b/')  # a click inside the store
        _page(at + timedelta(hours=2), self.visitor, {'ch': 'organic', 's': 'google'}, '/c/')
        services.roll_daily(day=self.today)
        rows = self._rows()
        self.assertEqual(
            [(r.channel, r.source, r.landing, r.pageviews) for r in rows],
            [('social', 'facebook', '/a/', 2), ('organic', 'google', '/c/', 1)],
        )
        sessions = DailyMetric.objects.get(day=self.today, metric='sessions', dimension='')
        self.assertEqual(sessions.value_int, len(rows))
        self.assertNotIn('returning', {r.visitor for r in rows})  # stored as a hash

    def test_a_first_page_from_the_store_is_direct_and_one_before_this_release_is_not_known(self):
        other = AnalyticsSession.objects.create(cookie_id='old')
        at = self.start + timedelta(hours=1)
        _page(at, self.visitor, {})
        _event(at, session=other)  # a pageview recorded before pages carried an arrival
        services.roll_daily(day=self.today)
        self.assertEqual(
            sorted(r.channel for r in self._rows()),
            ['direct', 'unknown'],
        )

    def test_a_visit_over_midnight_keeps_the_source_it_started_with(self):
        yesterday = self.today - timedelta(days=1)
        _page(self.start - timedelta(minutes=10), self.visitor, {'ch': 'email', 's': 'newsletter'})
        _page(self.start + timedelta(minutes=5), self.visitor, {})
        services.roll_daily(day=yesterday)
        services.roll_daily(day=self.today)
        (row,) = self._rows()
        self.assertEqual((row.channel, row.source), ('email', 'newsletter'))

    def test_orders_land_in_their_visit_and_count_net_of_refunds(self):
        order = Order.objects.create(
            email='src@example.com',
            subtotal=Money(Decimal('40.00'), 'EUR'),
            total=Money(Decimal('40.00'), 'EUR'),
            status='delivered',
            payment_status='paid',
        )
        Refund.objects.create(order=order, amount=Money(Decimal('10.00'), 'EUR'), is_processed=True)
        at = self.start + timedelta(hours=1)
        _page(at, self.visitor, {'ch': 'organic', 's': 'google'})
        _event(
            at + timedelta(minutes=1),
            session=self.visitor,
            kind='search',
            query='lantern',
            payload={'results': 3},
        )
        _event(
            at + timedelta(minutes=2),
            session=self.visitor,
            kind='search',
            query='zzqx',
            payload={'results': 0},
        )
        _event(
            at + timedelta(minutes=5),
            session=self.visitor,
            kind='purchase',
            name='order.placed',
            payload={'order': str(order.pk)},
        )
        other = AnalyticsSession.objects.create(cookie_id='browser')
        _page(at, other, {'ch': 'organic', 's': 'bing'})
        services.roll_daily(day=self.today)

        report = sources_report(days=1, by='channel')
        (organic,) = report['rows']
        self.assertEqual(
            (organic['label'], organic['visits'], organic['purchases']), ('Organic search', 2, 1)
        )
        self.assertEqual(organic['conversion'], 50.0)
        self.assertEqual(organic['sales'], Money(Decimal('30.00'), 'EUR'))
        by_source = {r['label']: r for r in sources_report(days=1, by='source')['rows']}
        self.assertEqual(by_source['google']['sales'], Money(Decimal('30.00'), 'EUR'))
        self.assertIsNone(by_source['bing']['sales'])

        self.assertEqual(
            search_terms(days=1, kind='led_to_sale'),
            [{'query': 'lantern', 'count': 1}, {'query': 'zzqx', 'count': 1}],
        )
        self.assertEqual(search_terms(days=1, kind='no_results'), [{'query': 'zzqx', 'count': 1}])

    def test_the_home_tiles_ai_visits_count_visits(self):
        at = self.start + timedelta(hours=1)
        _page(at, self.visitor, {'ch': 'ai', 's': 'chatgpt'})
        _page(at + timedelta(hours=1), self.visitor, {'ch': 'ai', 's': 'chatgpt'})
        services.roll_daily(day=self.today)
        row = DailyMetric.objects.get(day=self.today, metric='top_sources')
        self.assertEqual((row.dimension, row.value_int), ('ai:chatgpt', 2))

    def test_old_visit_rows_go_with_old_visitors(self):
        AnalyticsVisit.objects.create(
            day=self.today - timedelta(days=400),
            visitor='x',
            started_at=self.start,
            last_seen_at=self.start,
            channel='direct',
        )
        AnalyticsVisit.objects.create(
            day=self.today,
            visitor='y',
            started_at=self.start,
            last_seen_at=self.start,
            channel='direct',
        )
        services.trim_old_visitors(keep_days=395)
        self.assertEqual(list(AnalyticsVisit.objects.values_list('visitor', flat=True)), ['y'])


class SourcesPagesTests(TestCase):
    pages = ('/dashboard/apps/analytics/sources/', '/dashboard/apps/analytics/search-terms/')

    def test_anonymous_and_customers_are_kept_out(self):
        customer = get_user_model().objects.create_user(
            username='shopper', email='shopper@example.com', password='x'
        )
        for page in self.pages:
            with self.subTest(page=page):
                self.assertEqual(self.client.get(page).status_code, 302)
        self.client.force_login(customer)
        for page in self.pages:
            with self.subTest(page=page):
                self.assertNotEqual(self.client.get(page).status_code, 200)

    def test_staff_see_both_pages(self):
        staff = get_user_model().objects.create_superuser(
            username='boss', email='boss@example.com', password='x'
        )
        self.client.force_login(staff)
        session = AnalyticsSession.objects.create(cookie_id='page')
        start, _ = services.day_bounds(services.store_today())
        _page(start + timedelta(hours=1), session, {'ch': 'social', 's': 'pinterest'})
        services.roll_daily(day=services.store_today())
        resp = self.client.get(self.pages[0], {'days': 7, 'by': 'source'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-traffic-sources')
        self.assertContains(resp, 'pinterest')
        resp = self.client.get(self.pages[1], {'days': 'nonsense'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-search-terms')


class SourcesToolsAndCardTests(TestCase):
    def test_the_card_on_an_empty_store_and_with_visits(self):
        from plugins.installed.analytics.cards import sources_card

        self.assertIn('empty', sources_card(None))
        session = AnalyticsSession.objects.create(cookie_id='card')
        start, _ = services.day_bounds(services.store_today())
        _page(start + timedelta(hours=1), session, {'ch': 'referral', 's': 'blog.example'})
        services.roll_daily(day=services.store_today())
        card = sources_card(None)
        self.assertEqual(card['value'], '1')
        self.assertEqual(card['rows'], [('Other sites', '1 · 100.0%')])

    def test_lindas_tools(self):
        from plugins.installed.analytics.agent_tools import (
            analytics_search_trends_tool,
            analytics_traffic_sources_tool,
        )

        session = AnalyticsSession.objects.create(cookie_id='tool')
        start, _ = services.day_bounds(services.store_today())
        _page(start + timedelta(hours=1), session, {'ch': 'email', 's': 'newsletter'})
        _event(
            start + timedelta(hours=1, minutes=1),
            session=session,
            kind='search',
            query='tent',
            payload={'results': 0},
        )
        services.roll_daily(day=services.store_today())
        out = analytics_traffic_sources_tool.invoke({'days': 7, 'by': 'channel'}).output
        self.assertEqual([(r['label'], r['visits']) for r in out['rows']], [('Email', 1)])
        self.assertIsNone(out['totals']['sales'])
        found = analytics_search_trends_tool.invoke({'days': 7, 'kind': 'no_results'}).output
        self.assertEqual(found['searches'], [{'query': 'tent', 'count': 1}])
