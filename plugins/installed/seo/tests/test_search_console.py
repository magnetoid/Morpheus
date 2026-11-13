"""Google Search Console in the dashboard (v0.159.0).

The SEO Keywords page showed a position nothing ever wrote, and no page said
what Google showed the store for. The store now reads its Search Console
property with a service account and keeps Google's numbers for 16 months.
"""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from unittest import mock
from urllib.parse import unquote

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from djmoney.money import Money

from core.utils.site import store_today
from plugins.installed.seo import search_console as sc
from plugins.installed.seo.models import SearchConsoleRow, TrackedKeyword
from plugins.registry import app_registry

_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PEM = _PRIVATE.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
_KEY = {
    'type': 'service_account',
    'client_email': 'reader@shop-123.iam.gserviceaccount.com',
    'private_key_id': 'abc123',
    'private_key': _PEM,
    'token_uri': 'https://attacker.example/token',
}


class _Resp:
    def __init__(self, status=200, data=None):
        self.status_code = status
        self._data = data if data is not None else {}
        self.reason = 'OK' if status < 400 else 'Error'

    def json(self):
        return self._data


class FakeGoogle:
    """Answers the four Google endpoints the store calls, and records them."""

    def __init__(self, *, sites=None, rows=None, inspect=None, fail=None):
        self.calls = []
        self.sites = (
            sites
            if sites is not None
            else [{'siteUrl': 'sc-domain:shop.test', 'permissionLevel': 'siteOwner'}]
        )
        self.rows = rows or {}
        self.inspect = inspect or {}
        self.fail = fail

    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url == sc._TOKEN_URL:
            return _Resp(200, {'access_token': 'tok', 'expires_in': 3600})
        if self.fail:
            return _Resp(
                self.fail, {'error': {'message': 'User does not have sufficient permission'}}
            )
        if url.endswith('/webmasters/v3/sites'):
            return _Resp(200, {'siteEntry': self.sites})
        if url.endswith('/searchAnalytics/query'):
            dims = tuple(kwargs['json']['dimensions'])
            return _Resp(200, {'rows': self.rows.get(dims, [])})
        if url.endswith('/urlInspection/index:inspect'):
            return _Resp(200, self.inspect)
        return _Resp(404, {'error': {'message': 'no such endpoint'}})


def _row(keys, clicks, impressions, position):
    return {'keys': keys, 'clicks': clicks, 'impressions': impressions, 'position': position}


@override_settings(SITE_BASE_URL='https://www.shop.test')
class _Base(TestCase):
    def setUp(self):
        cache.clear()
        self.seo = app_registry.get('seo')
        self.addCleanup(cache.clear)
        self.addCleanup(self.seo.invalidate_config_cache)

    def connect(self, key=None, prop=''):
        self.seo.set_config('search_console_key', json.dumps(key or _KEY))
        self.seo.set_config('search_console_property', prop)
        self.addCleanup(self.seo.set_config, 'search_console_key', '')
        self.addCleanup(self.seo.set_config, 'search_console_property', '')

    def google(self, **kwargs):
        fake = FakeGoogle(**kwargs)
        patcher = mock.patch.object(sc, '_http', side_effect=fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake


class KeyTests(_Base):
    def test_a_key_is_a_service_account_json_or_nothing(self):
        self.assertEqual(sc.key_state(), 'missing')
        self.seo.set_config('search_console_key', 'not json')
        self.addCleanup(self.seo.set_config, 'search_console_key', '')
        self.assertEqual(sc.key_state(), 'invalid')
        self.seo.set_config('search_console_key', json.dumps({'type': 'authorized_user'}))
        self.assertEqual(sc.key_state(), 'invalid')
        self.connect()
        self.assertEqual(sc.key_state(), 'ok')
        self.assertEqual(sc.account_email(), _KEY['client_email'])

    def test_the_sign_in_goes_to_google_never_to_the_keys_token_address(self):
        self.connect()
        fake = self.google()
        sc.pull()
        token_calls = [c for c in fake.calls if 'token' in c[1]]
        self.assertEqual([c[1] for c in token_calls], ['https://oauth2.googleapis.com/token'])
        assertion = token_calls[0][2]['data']['assertion']
        claims = jwt.decode(
            assertion,
            _PRIVATE.public_key(),
            algorithms=['RS256'],
            audience='https://oauth2.googleapis.com/token',
        )
        self.assertEqual(claims['iss'], _KEY['client_email'])
        self.assertEqual(claims['scope'], 'https://www.googleapis.com/auth/webmasters.readonly')
        self.assertEqual(jwt.get_unverified_header(assertion)['kid'], 'abc123')
        # The token is reused, not fetched again on the next call.
        sc.pull()
        self.assertEqual(len([c for c in fake.calls if 'token' in c[1]]), 1)


class PropertyTests(_Base):
    def test_the_domain_property_then_an_address_property_for_this_host(self):
        self.connect()
        self.google()
        self.assertEqual(sc.property_url(_KEY, {}), 'sc-domain:shop.test')
        self.google(
            sites=[
                {'siteUrl': 'https://other.test/', 'permissionLevel': 'siteOwner'},
                {'siteUrl': 'https://www.shop.test/', 'permissionLevel': 'siteFullUser'},
            ]
        )
        self.assertEqual(sc.property_url(_KEY, {}), 'https://www.shop.test/')
        self.assertEqual(
            sc.property_url(_KEY, {'search_console_property': 'sc-domain:chosen.test'}),
            'sc-domain:chosen.test',
        )

    def test_no_property_for_this_store_says_what_to_do(self):
        self.google(sites=[{'siteUrl': 'https://other.test/', 'permissionLevel': 'siteOwner'}])
        with self.assertRaisesMessage(sc.SearchConsoleError, 'Add it as a user of the property'):
            sc.property_url(_KEY, {})


class PullTests(_Base):
    def setUp(self):
        super().setUp()
        self.today = store_today()
        self.day = self.today - timedelta(days=3)
        d = self.day.isoformat()
        self.rows = {
            ('date',): [_row([d], 30, 1000, 8.0)],
            ('date', 'query'): [
                _row([d, 'survival kit'], 12, 300, 4.0),
                _row([d, 'water filter'], 5, 200, 11.0),
            ],
            ('date', 'page'): [
                _row([d, 'https://www.shop.test/products/kit/'], 10, 400, 5.0),
                _row([d, 'https://shop.test/products/kit/'], 2, 100, 10.0),
                _row([d, 'https://www.shop.test/'], 18, 500, 9.0),
            ],
        }

    def test_without_a_key_nothing_is_fetched(self):
        fake = self.google()
        self.assertEqual(sc.pull(), {'ok': False, 'connected': False})
        self.assertEqual(fake.calls, [])

    def test_the_first_pull_fetches_ninety_settled_days_and_stores_each_kind(self):
        self.connect()
        fake = self.google(rows=self.rows)
        status = sc.pull(today=self.today)
        self.assertTrue(status['ok'])
        self.assertEqual(status['property'], 'sc-domain:shop.test')
        query = [c[2]['json'] for c in fake.calls if c[1].endswith('/searchAnalytics/query')]
        self.assertEqual(
            {(q['startDate'], q['endDate']) for q in query},
            {
                (
                    (self.today - timedelta(days=91)).isoformat(),
                    (self.today - timedelta(days=2)).isoformat(),
                )
            },
        )
        site_path = [c[1] for c in fake.calls if c[1].endswith('/searchAnalytics/query')][0]
        self.assertIn('sc-domain%3Ashop.test', site_path)
        self.assertEqual(
            unquote(site_path.split('/sites/')[1].split('/')[0]), 'sc-domain:shop.test'
        )
        total = SearchConsoleRow.objects.get(kind='total')
        self.assertEqual(
            (total.day, total.clicks, total.impressions, total.position), (self.day, 30, 1000, 8.0)
        )
        self.assertEqual(SearchConsoleRow.objects.filter(kind='query').count(), 2)
        kit = SearchConsoleRow.objects.get(kind='page', key='/products/kit/')
        # www and the bare domain are one page; its position is weighted by impressions.
        self.assertEqual((kit.clicks, kit.impressions, kit.position), (12, 500, 6.0))
        self.assertEqual(sc.last_pull()['ok'], True)

    def test_another_subdomains_pages_are_left_out(self):
        # A domain property holds every subdomain; a blog's /products/kit/ is not the store's.
        d = self.day.isoformat()
        self.rows[('date', 'page')] += [
            _row([d, 'https://blog.shop.test/products/kit/'], 90, 900, 1.0),
            _row([d, 'https://www.blog.shop.test/about/'], 9, 90, 2.0),
        ]
        self.connect()
        self.google(rows=self.rows)
        sc.pull(today=self.today)
        pages = dict(SearchConsoleRow.objects.filter(kind='page').values_list('key', 'clicks'))
        self.assertEqual(pages, {'/products/kit/': 12, '/': 18})

    def test_a_paths_query_strings_are_one_row_with_its_visits_once(self):
        from plugins.installed.analytics.models import AnalyticsVisit

        d = self.day.isoformat()
        self.rows[('date', 'page')] = [
            _row([d, 'https://www.shop.test/products/?color=red'], 4, 100, 2.0),
            _row([d, 'https://www.shop.test/products/?color=blue'], 6, 300, 6.0),
            _row([d, 'https://shop.test/products/'], 0, 100, 10.0),
        ]
        self.connect()
        self.google(rows=self.rows)
        sc.pull(today=self.today)
        AnalyticsVisit.objects.create(
            visitor='a',
            channel='organic',
            source='google',
            landing='/products/',
            day=self.day,
            started_at='2026-01-01T00:00Z',
            last_seen_at='2026-01-01T00:00Z',
        )
        (row,) = sc.report(days=7, by='page')['rows']
        self.assertEqual(
            (row['key'], row['clicks'], row['impressions'], row['position'], row['visits']),
            ('/products/', 10, 500, 6.0, 1),
        )

    def test_a_later_pull_refetches_the_last_unsettled_days_and_drops_old_rows(self):
        self.connect()
        SearchConsoleRow.objects.create(day=self.day, kind='total', clicks=1, impressions=1)
        SearchConsoleRow.objects.create(
            day=self.today - timedelta(days=500), kind='total', clicks=9, impressions=9
        )
        fake = self.google(rows=self.rows)
        sc.pull(today=self.today)
        query = [c[2]['json'] for c in fake.calls if c[1].endswith('/searchAnalytics/query')][0]
        self.assertEqual(query['startDate'], (self.today - timedelta(days=8)).isoformat())
        self.assertEqual(
            list(SearchConsoleRow.objects.filter(kind='total').values_list('day', 'clicks')),
            [(self.day, 30)],
        )

    def test_a_refusal_keeps_the_stored_numbers_and_says_why(self):
        self.connect()
        SearchConsoleRow.objects.create(day=self.day, kind='total', clicks=7, impressions=70)
        self.google(fail=403)
        with self.assertLogs('morpheus.seo.search_console', 'ERROR'):
            status = sc.pull(today=self.today)
        self.assertFalse(status['ok'])
        self.assertIn('403', status['detail'])
        self.assertIn('sufficient permission', sc.last_pull()['detail'])
        self.assertEqual(SearchConsoleRow.objects.get().clicks, 7)

    def test_tracked_keywords_get_googles_position_or_none(self):
        self.connect()
        seen = TrackedKeyword.objects.create(keyword='Survival Kit')
        unseen = TrackedKeyword.objects.create(keyword='tent')
        self.google(rows=self.rows)
        sc.pull(today=self.today)
        seen.refresh_from_db()
        unseen.refresh_from_db()
        self.assertEqual(seen.last_position, 4)
        self.assertIsNotNone(seen.last_checked_at)
        self.assertIsNone(unseen.last_position)
        self.assertIsNotNone(unseen.last_checked_at)


class ReportTests(_Base):
    def setUp(self):
        super().setUp()
        self.end = store_today() - timedelta(days=2)
        for n, (clicks, imps, pos) in enumerate([(10, 100, 4.0), (30, 300, 8.0)]):
            day = self.end - timedelta(days=n)
            SearchConsoleRow.objects.create(
                day=day, kind='total', clicks=clicks, impressions=imps, position=pos
            )
        SearchConsoleRow.objects.create(
            day=self.end - timedelta(days=10), kind='total', clicks=5, impressions=50, position=20
        )
        SearchConsoleRow.objects.create(
            day=self.end, kind='page', key='/products/kit/', clicks=8, impressions=80, position=3
        )
        SearchConsoleRow.objects.create(
            day=self.end, kind='query', key='kit', clicks=6, impressions=60, position=2
        )

    def test_totals_against_the_period_before_with_a_weighted_position(self):
        report = sc.report(days=7, by='query')
        self.assertEqual(
            report['totals'], {'clicks': 40, 'impressions': 400, 'ctr': 10.0, 'position': 7.0}
        )
        self.assertEqual(report['before']['clicks'], 5)
        self.assertEqual(
            report['rows'],
            [{'key': 'kit', 'clicks': 6, 'impressions': 60, 'ctr': 10.0, 'position': 2.0}],
        )

    def test_a_page_carries_the_visits_and_sales_googles_results_sent_it(self):
        from plugins.installed.analytics.models import AnalyticsVisit
        from plugins.installed.orders.models import Order

        order = Order.objects.create(
            email='g@example.com',
            subtotal=Money(Decimal('25.00'), 'EUR'),
            total=Money(Decimal('25.00'), 'EUR'),
            status='delivered',
            payment_status='paid',
        )
        common = {
            'day': self.end,
            'started_at': '2026-01-01T00:00Z',
            'last_seen_at': '2026-01-01T00:00Z',
        }
        AnalyticsVisit.objects.create(
            visitor='a',
            channel='organic',
            source='google',
            landing='/products/kit/',
            purchases=1,
            orders=[str(order.pk)],
            **common,
        )
        AnalyticsVisit.objects.create(
            visitor='b', channel='organic', source='google', landing='/products/kit/', **common
        )
        AnalyticsVisit.objects.create(
            visitor='c', channel='social', source='facebook', landing='/products/kit/', **common
        )
        (row,) = sc.report(days=7, by='page')['rows']
        self.assertEqual((row['key'], row['visits'], row['purchases']), ('/products/kit/', 2, 1))
        self.assertEqual(row['sales'], Money(Decimal('25.00'), 'EUR'))

    def test_nothing_stored_says_so(self):
        SearchConsoleRow.objects.all().delete()
        self.assertEqual(sc.report()['has_data'], False)


class InspectTests(_Base):
    def test_a_path_on_the_store_is_inspected_as_its_full_address(self):
        self.connect()
        fake = self.google(
            inspect={
                'inspectionResult': {
                    'inspectionResultLink': 'https://search.google.com/search-console/inspect?x=1',
                    'indexStatusResult': {
                        'verdict': 'PASS',
                        'coverageState': 'Submitted and indexed',
                        'googleCanonical': 'https://www.shop.test/products/kit/',
                    },
                }
            }
        )
        out = sc.inspect_url('/products/kit/')
        self.assertEqual((out['verdict'], out['coverage']), ('PASS', 'Submitted and indexed'))
        self.assertTrue(out['link'].startswith('https://search.google.com/'))
        body = [c[2]['json'] for c in fake.calls if c[1].endswith(':inspect')][0]
        self.assertEqual(
            body,
            {
                'inspectionUrl': 'https://www.shop.test/products/kit/',
                'siteUrl': 'sc-domain:shop.test',
            },
        )

    def test_another_sites_page_and_a_foreign_link_are_refused(self):
        self.connect()
        self.google(inspect={'inspectionResult': {'inspectionResultLink': 'https://evil.test/'}})
        with self.assertRaisesMessage(sc.SearchConsoleError, "store's own pages"):
            sc.inspect_url('https://other.test/x/')
        self.assertEqual(sc.inspect_url('https://shop.test/x/')['link'], '')


class PageTests(_Base):
    url = '/dashboard/seo/search-performance/'

    def setUp(self):
        super().setUp()
        self.staff = get_user_model().objects.create_superuser(
            username='seoboss', email='seoboss@example.com', password='x'
        )

    def test_anonymous_and_customers_are_kept_out(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        shopper = get_user_model().objects.create_user(
            username='s', email='s@example.com', password='x'
        )
        self.client.force_login(shopper)
        self.assertNotEqual(self.client.get(self.url).status_code, 200)

    def test_without_a_key_the_page_says_how_to_connect(self):
        self.client.force_login(self.staff)
        resp = self.client.get(self.url)
        self.assertContains(resp, 'data-search-console-connect')
        self.assertContains(resp, 'Users and permissions')

    def test_connected_the_page_shows_googles_numbers_fetches_and_inspects(self):
        self.connect()
        day = (store_today() - timedelta(days=3)).isoformat()
        self.google(
            rows={
                ('date',): [_row([day], 3, 90, 6.0)],
                ('date', 'query'): [_row([day, 'lantern'], 3, 90, 6.0)],
            },
            inspect={
                'inspectionResult': {
                    'indexStatusResult': {'verdict': 'NEUTRAL', 'coverageState': 'Discovered'}
                }
            },
        )
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(self.url, {'action': 'pull'}).status_code, 302)
        resp = self.client.get(self.url, {'days': 28, 'by': 'query'})
        self.assertContains(resp, 'data-search-performance-rows')
        self.assertContains(resp, 'lantern')
        self.assertContains(resp, _KEY['client_email'])
        # sc-domain:shop.test: Google's totals count every subdomain of it.
        self.assertContains(resp, 'any other subdomain of it')
        resp = self.client.post(self.url, {'action': 'inspect', 'url': '/products/kit/'})
        self.assertContains(resp, 'data-url-inspection')
        self.assertContains(resp, 'Discovered')

    def test_the_keywords_page_shows_googles_figures(self):
        self.connect()
        TrackedKeyword.objects.create(keyword='lantern', last_position=6)
        end = store_today() - timedelta(days=2)
        SearchConsoleRow.objects.create(day=end, kind='total', clicks=3, impressions=90, position=6)
        SearchConsoleRow.objects.create(
            day=end, kind='query', key='lantern', clicks=3, impressions=90, position=6
        )
        self.client.force_login(self.staff)
        resp = self.client.get('/dashboard/seo/keywords/')
        self.assertContains(resp, '<td>90</td>', html=False)


class ToolTests(_Base):
    def test_search_performance_says_when_it_is_not_connected(self):
        from plugins.installed.seo.agent_tools import search_performance_tool

        out = search_performance_tool.invoke({'days': 7}).output
        self.assertFalse(out['connected'])
        self.assertIn('Settings → SEO', out['note'])

    def test_search_performance_reads_the_stored_numbers(self):
        from plugins.installed.seo.agent_tools import search_performance_tool

        self.connect()
        end = store_today() - timedelta(days=2)
        SearchConsoleRow.objects.create(day=end, kind='total', clicks=4, impressions=40, position=5)
        SearchConsoleRow.objects.create(
            day=end, kind='page', key='/a/', clicks=4, impressions=40, position=5
        )
        out = search_performance_tool.invoke({'days': 7, 'by': 'page'}).output
        self.assertTrue(out['connected'])
        self.assertEqual(out['end'], end.isoformat())
        self.assertEqual(out['rows'][0]['key'], '/a/')
        self.assertIsNone(out['rows'][0]['sales'])

    def test_settings_list_never_shows_the_key(self):
        from core.assistant.tools.ecommerce import settings_list_tool

        self.connect()
        listed = json.dumps(settings_list_tool.invoke({}).output)
        self.assertNotIn('PRIVATE KEY', listed)
        self.assertNotIn(_KEY['client_email'], listed)
        self.assertNotIn('private_key', listed)

    def test_inspect_url_explains_a_refusal(self):
        from core.agents.tools import ToolError
        from plugins.installed.seo.agent_tools import inspect_url_tool

        with self.assertRaisesMessage(ToolError, 'not connected'):
            inspect_url_tool.invoke({'url': '/x/'})
