"""The affiliate portal: one shell, honest numbers, a link builder that only
makes links to this store, and no shop's vertical in the wording.

The portal used to promise payouts "on the 1st", +10% for store credit and a
30-day cookie whatever the program said; its link form accepted any URL, so an
affiliate could point the store's own /r/ redirect at another site; and the
dashboard and analytics showed two different "earned" figures, one of them
read from a balance column the merchant dashboard never updates.
"""

from __future__ import annotations

import re
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.affiliates.models import (
    Affiliate,
    AffiliateClick,
    AffiliateConversion,
    AffiliateLink,
    AffiliatePayout,
    AffiliateProgram,
)
from plugins.installed.affiliates.services import store_path
from plugins.installed.orders.models import Order, OrderItem

PAGES = (
    '/affiliates/me/',
    '/affiliates/me/links/',
    '/affiliates/me/coupon/',
    '/affiliates/me/conversions/',
    '/affiliates/me/analytics/',
    '/affiliates/me/payouts/',
    '/affiliates/me/creatives/',
    '/affiliates/me/widgets/',
    '/affiliates/me/leaderboard/',
    '/affiliates/me/settings/',
)
_ROBOTS = re.compile(r'<meta name="robots" content="([^"]*)"')
_VERTICAL = re.compile(r'\b(books?|readers?|imprints?|publishers?)\b', re.I)


_STORE_DATA = re.compile(r'<(option|datalist)\b[^>]*>.*?</\1>', re.S)


def _portal(body: str) -> str:
    """The portal's own markup — the theme around it has its own copy."""
    start = body.index('class="pp"')
    return body[start : body.index('data-pp-end', start)]


def _portal_words(body: str) -> str:
    """The portal's own wording: its markup without the store's data (category
    and product names in pickers), which is whatever the merchant sells."""
    return _STORE_DATA.sub('', _portal(body))


class _Base(TestCase):
    def setUp(self):
        self.program = AffiliateProgram.objects.create(
            name='Partners',
            slug='partners',
            commission_type='percent',
            commission_value=Decimal('10'),
            cookie_window_days=45,
            minimum_payout=Money(50, 'USD'),
        )
        self.user = get_user_model().objects.create_user(
            username='aff@example.com', email='aff@example.com', password='pw'
        )
        self.affiliate = Affiliate.objects.create(
            program=self.program, user=self.user, handle='jane', status='approved'
        )
        self.link = AffiliateLink.objects.create(
            affiliate=self.affiliate, code='janelink', landing_url='/', label='Newsletter'
        )
        self.client.force_login(self.user)

    def _conversion(self, *, commission, status='approved', days_ago=0, affiliate=None, link=None):
        affiliate = affiliate or self.affiliate
        n = AffiliateConversion.objects.count() + 1
        order = Order.objects.create(
            email=f'buyer{n}@example.com',
            subtotal=Money(commission * 10, 'USD'),
            total=Money(commission * 10, 'USD'),
        )
        conversion = AffiliateConversion.objects.create(
            affiliate=affiliate,
            link=link or self.link,
            order=order,
            commission=Money(commission, 'USD'),
            status=status,
        )
        if days_ago:
            AffiliateConversion.objects.filter(pk=conversion.pk).update(
                created_at=timezone.now() - timedelta(days=days_ago)
            )
        return conversion

    def _clicks(self, n, *, days_ago=0, link=None):
        clicks = AffiliateClick.objects.bulk_create(
            [AffiliateClick(link=link or self.link) for _ in range(n)]
        )
        if days_ago:
            AffiliateClick.objects.filter(pk__in=[c.pk for c in clicks]).update(
                occurred_at=timezone.now() - timedelta(days=days_ago)
            )


class PortalShellTests(_Base):
    def test_every_page_renders_in_the_shell_with_its_tab_current(self):
        for path in PAGES:
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 200)
                body = r.content.decode()
                self.assertIn('data-portal="affiliate"', body)
                self.assertIn('data-portal-status="approved"', body)
                self.assertEqual(_portal(body).count('aria-current="page"'), 1)
                self.assertIn('data-pp-tab="settings"', body)

    def test_each_page_has_one_robots_tag_and_it_says_noindex(self):
        # The templates used to add a raw robots meta beside the head
        # document's own: two contradictory robots tags on every page.
        for path in PAGES:
            with self.subTest(path=path):
                robots = _ROBOTS.findall(self.client.get(path).content.decode())
                self.assertEqual(len(robots), 1, robots)
                self.assertIn('noindex', robots[0])

    def test_no_page_speaks_a_bookshop(self):
        for path in PAGES:
            with self.subTest(path=path):
                portal = _portal_words(self.client.get(path).content.decode())
                self.assertIsNone(_VERTICAL.search(portal), _VERTICAL.findall(portal))

    def test_a_pending_affiliate_sees_the_application_not_the_tabs(self):
        Affiliate.objects.filter(pk=self.affiliate.pk).update(status='pending')
        body = self.client.get('/affiliates/me/').content.decode()
        self.assertIn('data-affiliate-state="pending"', body)
        self.assertIn('data-portal-status="pending"', body)
        self.assertNotIn('data-pp-tab=', body)

    def test_someone_without_an_account_is_invited_to_apply(self):
        stranger = get_user_model().objects.create_user(
            username='s@example.com', email='s@example.com', password='pw'
        )
        self.client.force_login(stranger)
        body = self.client.get('/affiliates/me/').content.decode()
        self.assertIn('data-affiliate-state="none"', body)
        self.assertIn('href="/affiliates/apply/"', body)


class NumbersTests(_Base):
    def test_kpis_compare_the_period_with_the_one_before(self):
        self._clicks(4)
        self._clicks(2, days_ago=40)  # inside the previous 30 days
        self._conversion(commission=5)
        body = self.client.get('/affiliates/me/?days=30').content.decode()
        clicks = body[body.index('data-kpi="clicks"') :]
        self.assertIn('data-kpi-value>4<', clicks[:400])
        self.assertIn('data-kpi-delta="up"', clicks[:900])
        self.assertIn('100%', clicks[:900])

    def test_earnings_come_from_the_conversions_not_the_balance_column(self):
        # The merchant dashboard approves by setting the status, so
        # accrued_balance stays 0 — the portal must still show the money.
        self._conversion(commission=Decimal('12.50'))
        self.assertEqual(self.affiliate.accrued_balance.amount, 0)
        for path in ('/affiliates/me/', '/affiliates/me/payouts/'):
            with self.subTest(path=path):
                body = self.client.get(path).content.decode()
                ready = body[body.index('data-balance="ready"') :][:120]
                self.assertIn('12.50', ready)

    def test_commission_in_review_is_counted_apart(self):
        self._conversion(commission=Decimal('7'), status='pending')
        body = self.client.get('/affiliates/me/').content.decode()
        self.assertIn('7.00', body[body.index('data-balance="review"') :][:120])
        self.assertIn('0.00', body[body.index('data-balance="ready"') :][:120])

    def test_the_cookie_window_is_the_programs(self):
        body = self.client.get('/affiliates/me/').content.decode()
        self.assertIn('45 days after a click', body)

    def test_what_customers_bought_comes_from_the_referred_orders(self):
        conversion = self._conversion(commission=3)
        OrderItem.objects.create(
            order=conversion.order,
            product_name='Golden Tincture',
            quantity=2,
            unit_price=Money(15, 'USD'),
            total_price=Money(30, 'USD'),
        )
        body = self.client.get('/affiliates/me/analytics/').content.decode()
        self.assertIn('Golden Tincture', body)

    def test_another_affiliates_activity_never_shows(self):
        other_user = get_user_model().objects.create_user(
            username='o@example.com', email='o@example.com', password='pw'
        )
        other = Affiliate.objects.create(
            program=self.program, user=other_user, handle='rival', status='approved'
        )
        rival_link = AffiliateLink.objects.create(
            affiliate=other, code='rivalcode', landing_url='/', label='Rival placement'
        )
        self._clicks(5, link=rival_link)
        self._conversion(commission=99, affiliate=other, link=rival_link)
        for path in ('/affiliates/me/', '/affiliates/me/links/', '/affiliates/me/analytics/'):
            with self.subTest(path=path):
                body = self.client.get(path).content.decode()
                self.assertNotIn('Rival placement', body)
                self.assertNotIn('rivalcode', body)
                self.assertNotIn('99.00', body)

    def test_conversions_filter_paid_includes_a_paid_payout(self):
        conversion = self._conversion(commission=60)
        payout = AffiliatePayout.objects.create(
            affiliate=self.affiliate, amount=Money(60, 'USD'), status='paid'
        )
        AffiliateConversion.objects.filter(pk=conversion.pk).update(payout=payout)
        body = self.client.get('/affiliates/me/conversions/?status=paid').content.decode()
        self.assertIn(f'data-conversion="{conversion.order.order_number}"', body)
        body = self.client.get('/affiliates/me/conversions/?status=approved').content.decode()
        self.assertNotIn(f'data-conversion="{conversion.order.order_number}"', body)


class CopyTests(_Base):
    def test_no_promise_the_store_does_not_keep(self):
        for path in ('/affiliates/me/payouts/', '/affiliates/me/settings/', '/affiliates/me/'):
            with self.subTest(path=path):
                body = self.client.get(path).content.decode()
                self.assertNotIn('+10%', body)
                self.assertNotIn('1st of', body)

    def test_store_credit_is_not_labelled_with_a_bonus(self):
        self.assertEqual(dict(Affiliate.PAYOUT_METHOD_CHOICES)['credit'], 'Store credit')


class LinkBuilderTests(_Base):
    def _create(self, url, label='', **extra):
        data = {'landing_url': url, 'label': label, 'return_to': '/affiliates/me/links/'}
        data.update(extra)
        return self.client.post('/affiliates/me/links/new/', data)

    def test_a_page_of_this_store_becomes_a_tracked_link(self):
        r = self._create('https://testserver/products/tincture/?utm_source=nl', label='Spring')
        link = AffiliateLink.objects.get(affiliate=self.affiliate, label='Spring')
        self.assertEqual(link.landing_url, '/products/tincture/?utm_source=nl')
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r['Location'].endswith(f'?new={link.code}'))
        page = self.client.get(r['Location']).content.decode()
        self.assertIn(f'data-new-link="{link.code}"', page)

    def test_another_site_is_refused(self):
        before = AffiliateLink.objects.count()
        for url in (
            'https://evil.example/login',
            '//evil.example/',
            'javascript:alert(1)',
            'https://testserver.evil.example/',
            '/r/janelink',
        ):
            with self.subTest(url=url):
                self._create(url)
        self.assertEqual(AffiliateLink.objects.count(), before)

    def test_the_same_untitled_link_is_not_made_twice(self):
        self._create('/products/tincture/')
        self._create('products/tincture/')
        self.assertEqual(AffiliateLink.objects.filter(landing_url='/products/tincture/').count(), 1)

    def test_a_malformed_affiliate_id_does_not_crash(self):
        r = self._create('/about/', affiliate_id='not-a-uuid')
        self.assertEqual(r.status_code, 302)
        self.assertTrue(AffiliateLink.objects.filter(landing_url='/about/').exists())

    def test_someone_elses_affiliate_id_makes_no_link_for_them(self):
        other_user = get_user_model().objects.create_user(
            username='o2@example.com', email='o2@example.com', password='pw'
        )
        other = Affiliate.objects.create(
            program=self.program, user=other_user, handle='other', status='approved'
        )
        self._create('/about/', affiliate_id=str(other.pk))
        self.assertFalse(AffiliateLink.objects.filter(affiliate=other).exists())

    def test_the_redirect_never_leaves_the_store(self):
        # A row saved before the guard (or written by hand) still cannot send
        # a visitor to another site.
        AffiliateLink.objects.create(
            affiliate=self.affiliate, code='oldrow', landing_url='https://evil.example/'
        )
        r = self.client.get('/r/oldrow')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], '/')

    def test_the_redirect_keeps_a_store_page(self):
        AffiliateLink.objects.create(
            affiliate=self.affiliate, code='good', landing_url='/products/tincture/'
        )
        self.assertEqual(self.client.get('/r/good')['Location'], '/products/tincture/')


class StorePathTests(SimpleTestCase):
    def test_accepts_paths_and_own_host_urls(self):
        host = 'shop.example'
        self.assertEqual(store_path('/a/b/', host), '/a/b/')
        self.assertEqual(store_path('a/b', host), '/a/b')
        self.assertEqual(store_path('https://shop.example/a?x=1#y', host), '/a?x=1#y')
        self.assertEqual(store_path('https://www.shop.example/a', host), '/a')
        self.assertEqual(store_path('shop.example/a', host), '/a')
        self.assertEqual(store_path('', host), '/')

    def test_refuses_anything_else(self):
        host = 'shop.example'
        for raw in (
            'https://other.example/a',
            'http://shop.example.other.example/',
            '//other.example/a',
            '/\\other.example',
            'javascript:alert(1)',
            'ftp://shop.example/a',
            '/r/abc',
            'x' * 600,
        ):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                store_path(raw, host)
