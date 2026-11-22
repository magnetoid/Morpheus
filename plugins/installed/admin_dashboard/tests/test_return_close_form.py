"""The dashboard closes a return by the customer's chosen outcome (C4, v0.188.0)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.orders.models import Order, OrderItem
from plugins.installed.orders.refunds import ReturnRequest
from plugins.testing import set_app_settings


def _usd(n):
    return Money(n, 'USD')


class _Base(TestCase):
    def setUp(self):
        book = Product.objects.create(
            name='Zephyr Atlas', slug='zephyr-atlas', sku='ZA', price=10, product_type='variable'
        )
        paperback = ProductVariant.objects.create(
            product=book, name='Paperback', sku='ZA-PB', price=_usd(10)
        )
        self.hardback = ProductVariant.objects.create(
            product=book, name='Hardback', sku='ZA-HB', price=_usd(10)
        )
        self.customer = get_user_model().objects.create_user(
            username='quillon', email='quillon@example.com', password='x'
        )
        self.order = Order.objects.create(
            customer=self.customer,
            email='quillon@example.com',
            subtotal=_usd(10),
            total=_usd(10),
            payment_status='paid',
            payment_gateway='manual',
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            product=book,
            variant=paperback,
            product_name='Zephyr Atlas',
            variant_name='Paperback',
            quantity=1,
            unit_price=_usd(10),
            total_price=_usd(10),
        )
        self.rr = ReturnRequest.objects.create(
            order=self.order,
            state='approved',
            items=[{'order_item_id': str(self.item.pk), 'quantity': 1}],
        )
        self.url = f'/dashboard/returns/{self.rr.pk}/'
        self.admin = get_user_model().objects.create_superuser(
            username='admin', email='admin@example.com', password='x'
        )

    def choose_exchange(self):
        from plugins.installed.returns_portal.models import ReturnResolution

        ReturnResolution.objects.create(
            request=self.rr,
            resolution='exchange',
            exchange_choices=[
                {'order_item_id': str(self.item.pk), 'exchange_variant_id': str(self.hardback.pk)}
            ],
        )

    def exchange_orders(self):
        return Order.objects.filter(metadata__exchange_of=self.rr.rma_number)

    def page(self):
        self.client.force_login(self.admin)
        return self.client.get(self.url).content.decode()


class ReturnCloseFormTests(_Base):
    def test_detail_shows_the_customers_chosen_exchange(self):
        self.choose_exchange()
        body = self.page()
        self.assertIn('data-return-resolution="exchange"', body)
        self.assertIn('Hardback', body)
        self.assertIn('value="exchange" checked', body)

    def test_close_exchange_creates_the_linked_order(self):
        self.choose_exchange()
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {'action': 'close', 'outcome': 'exchange'})
        self.assertEqual(response.status_code, 302)
        new = self.exchange_orders().get()
        self.assertEqual(new.items.get().variant_id, self.hardback.pk)
        self.rr.refresh_from_db()
        self.assertEqual(self.rr.state, 'refunded')

    def test_staff_can_waive_the_fee(self):
        set_app_settings(self, 'returns_portal', exchange_fee='fixed', exchange_fee_amount=6)
        self.choose_exchange()
        self.assertIn('value="6.00"', self.page())
        self.client.post(self.url, {'action': 'close', 'outcome': 'exchange', 'fee': '0'})
        new = self.exchange_orders().get()
        self.assertEqual(new.total, _usd(0))
        self.assertEqual(new.payment_status, 'paid')

    def test_fee_is_charged_unless_waived(self):
        set_app_settings(self, 'returns_portal', exchange_fee='fixed', exchange_fee_amount=6)
        self.choose_exchange()
        self.client.force_login(self.admin)
        self.client.post(self.url, {'action': 'close', 'outcome': 'exchange', 'fee': '6.00'})
        self.assertEqual(self.exchange_orders().get().total, _usd(6))

    def test_switching_outcome_takes_that_outcomes_fee_not_the_prefilled_one(self):
        set_app_settings(self, 'returns_portal', exchange_fee='fixed', exchange_fee_amount=6)
        self.choose_exchange()
        self.client.force_login(self.admin)
        self.client.post(
            self.url,
            {
                'action': 'close',
                'outcome': 'refund',
                'fee': '6.00',
                'prefill_outcome': 'exchange',
                'prefill_fee': '6.00',
            },
        )
        self.rr.refresh_from_db()
        self.assertEqual(self.rr.refund.amount, _usd(10))

    def test_a_fee_staff_typed_is_kept_when_they_switch(self):
        set_app_settings(self, 'returns_portal', exchange_fee='fixed', exchange_fee_amount=6)
        self.choose_exchange()
        self.client.force_login(self.admin)
        self.client.post(
            self.url,
            {
                'action': 'close',
                'outcome': 'refund',
                'fee': '3',
                'prefill_outcome': 'exchange',
                'prefill_fee': '6.00',
            },
        )
        self.rr.refresh_from_db()
        self.assertEqual(self.rr.refund.amount, _usd(7))

    def test_without_portal_no_exchange_is_offered(self):
        from plugins.registry import app_registry

        self.choose_exchange()
        app_registry.deactivate('returns_portal')
        self.addCleanup(app_registry.activate, 'returns_portal')
        body = self.page()
        self.assertNotIn('value="exchange"', body)
        self.assertIn('value="refund" checked', body)
        self.client.post(self.url, {'action': 'close', 'outcome': 'exchange'})
        self.assertFalse(self.exchange_orders().exists())

    def test_old_refund_buttons_still_close(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {'action': 'refund_money'})
        self.rr.refresh_from_db()
        self.assertEqual(self.rr.state, 'refunded')
        self.assertEqual(self.rr.refund.amount, _usd(10))

    def test_a_bad_fee_is_refused(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {'action': 'close', 'outcome': 'refund', 'fee': 'x'})
        self.assertEqual(response.status_code, 200)
        self.rr.refresh_from_db()
        self.assertEqual(self.rr.state, 'approved')


class ReturnClosePermissionTests(_Base):
    def setUp(self):
        super().setUp()
        from plugins.installed.rbac.models import Role
        from plugins.registry import app_registry

        Role.ensure_system_roles()
        rbac = app_registry.get('rbac')
        rbac.set_config('enforcement_mode', 'enforce')
        self.addCleanup(rbac.invalidate_config_cache)
        self.addCleanup(rbac.set_config, 'enforcement_mode', 'log')

    def test_anonymous_is_sent_to_sign_in(self):
        response = self.client.post(self.url, {'action': 'close', 'outcome': 'refund'})
        self.assertEqual(response.status_code, 302)
        self.rr.refresh_from_db()
        self.assertEqual(self.rr.state, 'approved')

    def test_staff_without_orders_write_is_refused_while_rbac_enforces(self):
        staff = get_user_model().objects.create_user(
            username='no-role', email='no-role@example.com', password='x', is_staff=True
        )
        self.client.force_login(staff)
        response = self.client.post(self.url, {'action': 'close', 'outcome': 'refund'})
        self.assertEqual(response.status_code, 403)
        self.rr.refresh_from_db()
        self.assertEqual(self.rr.state, 'approved')
