"""The vendor portal: the shell, the orders to send, stock through the
inventory app's answer, and four holes it used to have.

* The account tile read a model marketplace does not define and swallowed the
  error, so it never showed for anyone.
* A vendor the merchant switched on from the customer page (no application)
  landed on "You haven't applied" instead of their shop.
* Each payout request was for the whole balance and nothing stopped a second
  one while the first was open — the same money asked for twice.
* A crafted POST could set a store-owned status ("refunded") or a
  ``javascript:`` tracking link.
"""

from __future__ import annotations

import re
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.test import RequestFactory, TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.catalog.models import Product, Vendor
from plugins.installed.marketplace import services
from plugins.installed.marketplace.models import (
    VendorApplication,
    VendorOrder,
    VendorPayout,
    VendorPayoutAccount,
)
from plugins.installed.orders.models import Order

PAGES = (
    '/vendor/me/',
    '/vendor/me/orders/',
    '/vendor/me/products/',
    '/vendor/me/payouts/',
    '/vendor/me/settings/',
)
_ROBOTS = re.compile(r'<meta name="robots" content="([^"]*)"')
_VERTICAL = re.compile(r'\b(books?|readers?|imprints?|manuscripts?)\b', re.I)


def _portal(body: str) -> str:
    start = body.index('class="pp"')
    return body[start : body.index('data-pp-end', start)]


def _user(email):
    return get_user_model().objects.create_user(username=email, email=email, password='pw')


class _VendorBase(TestCase):
    def setUp(self):
        self.user = _user('maker@example.com')
        # Switched on by the merchant from the customer page: no application.
        self.vendor = Vendor.objects.create(name='Hill Apothecary', slug='hill', owner=self.user)
        self.product = Product.objects.create(
            name='Rose Oil',
            slug='rose-oil',
            sku='ROSE-1',
            price=Money(20, 'USD'),
            status='active',
            vendor=self.vendor,
        )
        self.client.force_login(self.user)

    def _slice(self, *, gross=40, status='pending', paid=True, days_ago=0, vendor=None, items=None):
        n = VendorOrder.objects.count() + 1
        order = Order.objects.create(
            email=f'buyer{n}@example.com',
            subtotal=Money(gross, 'USD'),
            total=Money(gross, 'USD'),
            payment_status='paid' if paid else 'unpaid',
            shipping_address={'city': 'Porto', 'country': 'PT'},
        )
        slice_ = VendorOrder.objects.create(
            parent_order=order,
            vendor=vendor or self.vendor,
            gross=Money(gross, 'USD'),
            commission=Money(Decimal(gross) / 10, 'USD'),
            net=Money(Decimal(gross) * 9 / 10, 'USD'),
            status=status,
            items_snapshot=items
            or [
                {
                    'sku': 'ROSE-1',
                    'name': 'Rose Oil',
                    'quantity': 2,
                    'unit_price': '20.00',
                    'currency': 'USD',
                }
            ],
        )
        if days_ago:
            VendorOrder.objects.filter(pk=slice_.pk).update(
                created_at=timezone.now() - timedelta(days=days_ago)
            )
        return slice_


class AccountTileTests(_VendorBase):
    def _tile(self, user):
        request = RequestFactory().get('/account/')
        request.user = user
        return Template('{% include "marketplace/blocks/account_tile.html" %}').render(
            Context({'request': request})
        )

    def test_an_owner_gets_the_tile(self):
        self.assertIn('data-vendor-tile="approved"', self._tile(self.user))

    def test_an_applicant_gets_the_tile_with_the_application_status(self):
        applicant = _user('applicant@example.com')
        VendorApplication.objects.create(
            user=applicant, business_name='New Co', contact_email='applicant@example.com'
        )
        self.assertIn('data-vendor-tile="submitted"', self._tile(applicant))

    def test_anyone_else_gets_nothing(self):
        self.assertNotIn('data-vendor-tile', self._tile(_user('nobody@example.com')))


class ShellTests(_VendorBase):
    def test_a_vendor_without_an_application_gets_their_portal(self):
        body = self.client.get('/vendor/me/').content.decode()
        self.assertIn('data-portal="vendor"', body)
        self.assertIn('data-portal-status="active"', body)
        self.assertIn('data-pp-tab="orders"', body)

    def test_every_page_renders_with_one_robots_tag_saying_noindex(self):
        for path in PAGES:
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 200)
                robots = _ROBOTS.findall(r.content.decode())
                self.assertEqual(len(robots), 1, robots)
                self.assertIn('noindex', robots[0])

    def test_no_page_speaks_a_bookshop(self):
        self._slice()
        for path in (*PAGES, f'/vendor/me/products/{self.product.pk}/'):
            with self.subTest(path=path):
                portal = _portal(self.client.get(path).content.decode())
                self.assertIsNone(_VERTICAL.search(portal), _VERTICAL.findall(portal))

    def test_an_applicant_sees_where_the_application_stands(self):
        applicant = _user('waiting@example.com')
        VendorApplication.objects.create(
            user=applicant,
            business_name='Wait Co',
            contact_email='waiting@example.com',
            status='reviewing',
        )
        self.client.force_login(applicant)
        body = self.client.get('/vendor/me/').content.decode()
        self.assertIn('data-vendor-state="reviewing"', body)
        self.assertNotIn('data-pp-tab=', body)

    def test_a_paused_vendor_is_told_so(self):
        Vendor.objects.filter(pk=self.vendor.pk).update(is_active=False)
        body = self.client.get('/vendor/me/').content.decode()
        self.assertIn('data-vendor-state="paused"', body)


class OverviewTests(_VendorBase):
    def test_sales_count_only_orders_that_still_stand(self):
        self._slice(gross=40)
        self._slice(gross=60, status='cancelled')
        store_cancelled = self._slice(gross=80)
        Order.objects.filter(pk=store_cancelled.parent_order_id).update(status='cancelled')
        body = self.client.get('/vendor/me/').content.decode()
        sales = body[body.index('data-kpi="sales"') :][:400]
        self.assertIn('40.00', sales)

    def test_orders_to_send_show_paid_ones_with_a_ship_form(self):
        paid = self._slice()
        unpaid = self._slice(paid=False)
        self._slice(status='shipped')
        body = self.client.get('/vendor/me/').content.decode()
        self.assertIn(f'data-to-send="{paid.parent_order.order_number}"', body)
        self.assertIn(f'data-to-send="{unpaid.parent_order.order_number}"', body)
        self.assertIn(f'action="/vendor/me/orders/{paid.pk}/"', body)
        self.assertNotIn(f'action="/vendor/me/orders/{unpaid.pk}/"', body)

    def test_best_sellers_come_from_the_order_snapshots(self):
        self._slice()
        body = self.client.get('/vendor/me/').content.decode()
        self.assertIn('data-best-seller="ROSE-1"', body)


class OrdersTests(_VendorBase):
    def test_only_this_vendors_orders_are_listed(self):
        other = Vendor.objects.create(name='Other', slug='other', owner=_user('o@example.com'))
        mine = self._slice()
        theirs = self._slice(vendor=other)
        body = self.client.get('/vendor/me/orders/').content.decode()
        self.assertIn(f'data-vendor-order="{mine.parent_order.order_number}"', body)
        self.assertNotIn(f'data-vendor-order="{theirs.parent_order.order_number}"', body)
        csv = self.client.get('/vendor/me/orders/?export=csv').content.decode()
        self.assertIn(mine.parent_order.order_number, csv)
        self.assertNotIn(theirs.parent_order.order_number, csv)

    def test_mark_shipped_from_the_list_comes_back_to_it(self):
        vo = self._slice()
        r = self.client.post(
            f'/vendor/me/orders/{vo.pk}/',
            {
                'status': 'shipped',
                'tracking_number': 'TRK123',
                'next': '/vendor/me/orders/?status=open',
            },
        )
        self.assertEqual(r['Location'], '/vendor/me/orders/?status=open')
        vo.refresh_from_db()
        self.assertEqual((vo.status, vo.tracking_number), ('shipped', 'TRK123'))
        self.assertIsNotNone(vo.fulfilled_at)

    def test_a_next_off_the_portal_is_ignored(self):
        vo = self._slice()
        r = self.client.post(
            f'/vendor/me/orders/{vo.pk}/', {'status': 'shipped', 'next': 'https://evil.example/'}
        )
        self.assertEqual(r['Location'], f'/vendor/me/orders/{vo.pk}/')

    def test_the_store_owned_statuses_cannot_be_set(self):
        vo = self._slice()
        for status in ('refunded', 'pending', 'anything'):
            with self.subTest(status=status):
                self.client.post(f'/vendor/me/orders/{vo.pk}/', {'status': status})
                vo.refresh_from_db()
                self.assertEqual(vo.status, 'pending')

    def test_a_script_tracking_link_is_refused(self):
        vo = self._slice()
        self.client.post(
            f'/vendor/me/orders/{vo.pk}/',
            {'status': 'shipped', 'tracking_url': 'javascript:alert(1)'},
        )
        vo.refresh_from_db()
        self.assertEqual((vo.status, vo.tracking_url), ('pending', ''))

    def test_another_vendors_order_cannot_be_updated(self):
        other = Vendor.objects.create(name='Other', slug='other2', owner=_user('o2@example.com'))
        theirs = self._slice(vendor=other)
        r = self.client.post(f'/vendor/me/orders/{theirs.pk}/', {'status': 'shipped'})
        self.assertEqual(r.status_code, 404)
        theirs.refresh_from_db()
        self.assertEqual(theirs.status, 'pending')


class PayoutTests(_VendorBase):
    def setUp(self):
        super().setUp()
        VendorPayoutAccount.objects.create(
            vendor=self.vendor, method='paypal', accrued_balance=Money(120, 'USD')
        )

    def test_a_second_request_while_one_is_open_is_refused(self):
        self.client.post('/vendor/me/payouts/')
        self.client.post('/vendor/me/payouts/')
        self.assertEqual(VendorPayout.objects.filter(vendor=self.vendor).count(), 1)
        body = self.client.get('/vendor/me/payouts/').content.decode()
        self.assertIn('data-payout-blocker="open"', body)

    def test_the_service_refuses_it_too(self):
        services.request_vendor_payout(vendor=self.vendor, amount=Money(100, 'USD'))
        with self.assertRaises(ValueError):
            services.request_vendor_payout(vendor=self.vendor, amount=Money(20, 'USD'))

    def test_without_a_method_the_page_says_so(self):
        VendorPayoutAccount.objects.filter(vendor=self.vendor).update(method='unset')
        self.client.post('/vendor/me/payouts/')
        self.assertFalse(VendorPayout.objects.exists())
        body = self.client.get('/vendor/me/payouts/').content.decode()
        self.assertIn('data-payout-blocker="method"', body)


class StockTests(_VendorBase):
    def _stock(self, product, quantity):
        from plugins.installed.catalog.models import ProductVariant
        from plugins.installed.inventory.models import StockLevel, Warehouse

        variant = ProductVariant.objects.create(
            product=product, name='Std', sku=f'{product.sku}-V', price=Money(20, 'USD')
        )
        warehouse, _created = Warehouse.objects.get_or_create(
            code='MAIN', defaults={'name': 'Main'}
        )
        StockLevel.objects.create(variant=variant, warehouse=warehouse, quantity=quantity)

    def test_products_show_the_stock_inventory_reports(self):
        self._stock(self.product, 2)
        untracked = Product.objects.create(
            name='Clay Mask',
            slug='clay',
            sku='CLAY-1',
            price=Money(9, 'USD'),
            status='active',
            vendor=self.vendor,
        )
        body = self.client.get('/vendor/me/products/').content.decode()
        row = body[body.index('data-product="ROSE-1"') :][:2500]
        self.assertIn('data-stock="2"', row)
        clay = body[body.index('data-product="CLAY-1"') :][:2500]
        self.assertIn('data-stock=""', clay)
        self.assertTrue(untracked.pk)

    def test_low_stock_is_flagged_on_the_overview(self):
        self._stock(self.product, 1)
        body = self.client.get('/vendor/me/').content.decode()
        self.assertIn('data-low-stock="ROSE-1"', body)

    def test_without_inventory_the_page_shows_no_stock_column(self):
        from plugins.registry import app_registry

        self._stock(self.product, 2)
        app_registry.deactivate('inventory')
        self.addCleanup(app_registry.activate, 'inventory')
        body = self.client.get('/vendor/me/products/').content.decode()
        self.assertNotIn('data-stock=', body)
