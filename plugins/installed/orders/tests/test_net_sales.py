"""One sales figure for every report (v0.157.0).

Until then the home tiles, the Sales page and Linda's two sales summaries
counted every order, cancelled ones and unpaid ones left at checkout too, and
never took a refund off; the cohorts and the Pulse counted statuses no order
has ('paid', 'completed'), so a shipped order brought in nothing; one of
Linda's summaries left out cash on delivery and held cards; and the Sales page
printed "$" on a euro store.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.orders import reports


def _order(total, *, status='delivered', payment='paid', currency='EUR', customer=None, at=None):
    from plugins.installed.orders.models import Order

    order = Order.objects.create(
        email='n@example.com',
        customer=customer,
        subtotal=Money(total, currency),
        total=Money(total, currency),
        status=status,
        payment_status=payment,
    )
    if at is not None:
        Order.objects.filter(pk=order.pk).update(placed_at=at)
    return order


def _refund(order, amount, *, processed=True):
    from plugins.installed.orders.models import Refund

    return Refund.objects.create(
        order=order, amount=Money(amount, order.total.currency), is_processed=processed
    )


class CountedOrdersTests(TestCase):
    def test_only_placed_orders_that_were_not_cancelled_count(self):
        kept = [
            _order(10, status='confirmed', payment='unpaid'),  # cash on delivery
            _order(10, status='confirmed', payment='authorized'),  # card held
            _order(10, status='shipped'),
            _order(10, status='refunded', payment='refunded'),
            _order(10, status='pending', payment='paid'),  # paid before Stripe confirmed it
        ]
        _order(10, status='pending', payment='unpaid')  # left at the payment step
        _order(10, status='cancelled', payment='unpaid')
        _order(10, status='confirmed', payment='released')  # hold given back
        self.assertEqual(set(reports.counted().values_list('pk', flat=True)), {o.pk for o in kept})

    def test_net_takes_off_the_processed_refunds(self):
        a = _order(40)
        _order(25, status='processing')
        _refund(a, 15)
        _refund(a, 5, processed=False)
        _refund(_order(99, status='cancelled'), 99)
        sales = reports.net_sales()
        self.assertEqual(
            (sales.orders, sales.gross, sales.refunds, sales.net, sales.currency),
            (2, Decimal('65.00'), Decimal('15.00'), Decimal('50.00'), 'EUR'),
        )

    def test_a_second_currency_is_never_added_in(self):
        _order(10)
        _order(20)
        _order(7, currency='USD')
        sales = reports.net_sales()
        self.assertEqual((sales.currency, sales.net), ('EUR', Decimal('30.00')))
        self.assertEqual(sales.others, {'USD': Decimal('7.00')})

    def test_an_empty_store_has_no_sales(self):
        sales = reports.net_sales()
        self.assertEqual((sales.orders, sales.net, sales.currency), (0, Decimal('0.00'), ''))

    def test_by_order_and_by_day_on_the_stores_clock(self):
        late = _order(30, at=datetime(2026, 11, 10, 23, 30, tzinfo=UTC))
        early = _order(12, at=datetime(2026, 11, 10, 8, 0, tzinfo=UTC))
        _refund(late, 10)
        self.assertEqual(
            reports.net_by_order([late.pk, early.pk]),
            {str(late.pk): Decimal('20.00'), str(early.pk): Decimal('12.00')},
        )
        from plugins.installed.orders.models import Order

        belgrade = reports.net_by_day(Order.objects.all(), ZoneInfo('Europe/Belgrade'))
        # 23:30 UTC is already the 11th in Belgrade.
        self.assertEqual(belgrade[datetime(2026, 11, 10).date()], (1, Decimal('12.00')))
        self.assertEqual(belgrade[datetime(2026, 11, 11).date()], (1, Decimal('20.00')))

    def test_by_customer(self):
        users = get_user_model().objects
        ann = users.create_user(username='ann', email='ann@example.com', password='x')
        bob = users.create_user(username='bob', email='bob@example.com', password='x')
        first = _order(50, customer=ann, at=datetime(2026, 11, 1, 9, tzinfo=UTC))
        _order(20, customer=ann, at=datetime(2026, 11, 3, 9, tzinfo=UTC))
        _order(9, customer=ann, currency='USD', at=datetime(2026, 11, 5, 9, tzinfo=UTC))
        _order(400, status='cancelled', customer=bob)
        _refund(first, 15)
        bought = reports.by_customer([ann.pk, bob.pk])
        self.assertNotIn(str(bob.pk), bought)
        mine = bought[str(ann.pk)]
        self.assertEqual((mine.orders, mine.net, mine.currency), (2, Decimal('55.00'), 'EUR'))
        self.assertEqual(mine.last_order_at, datetime(2026, 11, 5, 9, tzinfo=UTC))


def _window(days=7):
    end = timezone.now() + timedelta(minutes=1)
    start = end - timedelta(days=days)
    return SimpleNamespace(
        start=start, end=end, prev_start=start - timedelta(days=days), prev_end=start
    )


class ReportReadersTests(TestCase):
    """Every sales figure a merchant or Linda reads is the same one."""

    def setUp(self):
        self.buyer = get_user_model().objects.create_user(
            username='ns', email='ns@example.com', password='x'
        )
        paid = _order(80, customer=self.buyer)
        _refund(paid, 30)
        _order(20, status='confirmed', payment='unpaid', customer=self.buyer)  # cash on delivery
        _order(500, status='cancelled', customer=self.buyer)
        _order(300, status='pending', payment='unpaid', customer=self.buyer)

    def test_home_tiles(self):
        from plugins.installed.orders.dashboard import on_dashboard_kpis

        tiles = {t['label']: t for t in on_dashboard_kpis([], date_range=_window())}
        self.assertEqual(tiles['Orders']['value'], '2')
        self.assertIn('70.00', tiles['Total sales']['value'])
        self.assertIn('€', tiles['Total sales']['value'])
        self.assertNotIn('$', tiles['Total sales']['value'])
        self.assertEqual(tiles['Total sales']['series'][-1], 70.0)

    def test_linda_summaries(self):
        from plugins.installed.agent_core.tools.analytics import revenue_summary_tool
        from plugins.installed.orders.agent_tools import analytics_summary_tool

        summary = analytics_summary_tool.invoke({'days_back': 7}).output
        self.assertEqual((summary['orders'], summary['revenue']), (2, '70.00'))
        self.assertEqual(summary['currency'], 'EUR')
        revenue = revenue_summary_tool.invoke({'days': 7}).output
        self.assertEqual((revenue['order_count'], revenue['revenue']), (2, '70.00'))

    def test_sales_page(self):
        staff = get_user_model().objects.create_superuser(
            username='boss', email='boss@example.com', password='x'
        )
        self.client.force_login(staff)
        resp = self.client.get('/dashboard/analytics/?period=7d')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('€70.00', body)
        self.assertNotIn('$', ''.join(t['label'] for t in resp.context['chart_yticks']))
        self.assertNotIn('500.00', body)

    def test_cohorts_and_traffic_page(self):
        from plugins.installed.analytics.services import summary_for
        from plugins.installed.analytics.services_cohorts import _sum_revenue, period_comparison

        now = timezone.now()
        self.assertEqual(
            _sum_revenue([self.buyer.pk], now - timedelta(days=1), now + timedelta(minutes=1)),
            Decimal('70.00'),
        )
        self.assertEqual(period_comparison(days=7)['orders_this'], 2)
        summary = summary_for(days=7)
        self.assertEqual(summary['orders'], 2)
        self.assertEqual(summary['revenue'], Money(Decimal('70.00'), 'EUR'))

    def test_contacts_spent(self):
        staff = get_user_model().objects.create_superuser(
            username='boss2', email='boss2@example.com', password='x'
        )
        self.client.force_login(staff)
        resp = self.client.get(f'/dashboard/customers/{self.buyer.pk}/')
        self.assertEqual(resp.status_code, 200)
        summary = resp.context['order_summary']
        self.assertEqual((summary['count'], summary['spent']), (2, Decimal('70.00')))
        self.assertIn('€70.00', resp.content.decode())
        # The list shows the same figure, whatever the stored lifetime value says.
        get_user_model().objects.filter(pk=self.buyer.pk).update(
            purchase_count=9, lifetime_value=Decimal('900.00')
        )
        resp = self.client.get('/dashboard/customers/')
        row = next(c for c in resp.context['customers'] if c['id'] == self.buyer.pk)
        self.assertEqual((row['order_count'], row['spent']), (2, Money('70.00', 'EUR')))

    def test_sales_forecast_and_cohorts_in_the_stores_currency(self):
        from plugins.installed.analytics.services import predictive_trends

        for days_ago in (1, 2, 3):
            _order(10, at=timezone.now() - timedelta(days=days_ago))
        forecast = predictive_trends(days=7)
        self.assertEqual(forecast['forecast'].currency.code, 'EUR')
        staff = get_user_model().objects.create_superuser(
            username='boss3', email='boss3@example.com', password='x'
        )
        self.client.force_login(staff)
        resp = self.client.get('/dashboard/analytics/v2/cohorts/?metric=revenue')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['currency_symbol'], '€')
        resp = self.client.get('/dashboard/analytics/v2/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.context['forecast']['forecast'])


class CustomerTotalsTests(TestCase):
    """A contact's stored purchase count and lifetime value follow the sales rule."""

    def setUp(self):
        self.buyer = get_user_model().objects.create_user(
            username='ct', email='ct@example.com', password='x'
        )

    def _stored(self):
        buyer = get_user_model().objects.get(pk=self.buyer.pk)
        return buyer.purchase_count, buyer.lifetime_value

    def test_order_events_refresh_the_contact(self):
        from morpheus.core import MorpheusEvents, hook_registry

        paid = _order(80, customer=self.buyer)
        with self.captureOnCommitCallbacks(execute=True):
            hook_registry.fire(MorpheusEvents.ORDER_PAID, order=paid)
        self.assertEqual(self._stored(), (1, Decimal('80.00')))
        refund = _refund(paid, 30)
        with self.captureOnCommitCallbacks(execute=True):
            hook_registry.fire(MorpheusEvents.PAYMENT_REFUNDED, order=paid, refund=refund)
        self.assertEqual(self._stored(), (1, Decimal('50.00')))
        from plugins.installed.orders.models import Order

        Order.objects.filter(pk=paid.pk).update(status='cancelled')
        with self.captureOnCommitCallbacks(execute=True):
            hook_registry.fire(MorpheusEvents.ORDER_CANCELLED, order=paid)
        self.assertEqual(self._stored(), (0, Decimal('0.00')))

    def test_the_nightly_refresh_heals_a_stale_contact(self):
        from plugins.installed.orders.tasks import refresh_customer_totals

        _order(25, status='confirmed', payment='unpaid', customer=self.buyer)  # cash on delivery
        ghost = get_user_model().objects.create_user(
            username='gh', email='gh@example.com', password='x'
        )
        get_user_model().objects.filter(pk=ghost.pk).update(
            purchase_count=3, lifetime_value=Decimal('300.00')
        )
        self.assertEqual(refresh_customer_totals(), 2)
        self.assertEqual(self._stored(), (1, Decimal('25.00')))
        ghost.refresh_from_db()
        self.assertEqual((ghost.purchase_count, ghost.lifetime_value), (0, Decimal('0.00')))


class CancelOutsideTransactionTests(TransactionTestCase):
    """A cancellation's event fires before the caller saves the order; with no
    surrounding transaction the contact's totals must still drop."""

    def test_cancel_then_save_lowers_the_stored_totals(self):
        buyer = get_user_model().objects.create_user(
            username='co', email='co@example.com', password='x'
        )
        order = _order(80, customer=buyer)
        _order(20, customer=buyer)
        from plugins.installed.orders.customer_totals import refresh

        refresh([buyer.pk])
        buyer.refresh_from_db()
        self.assertEqual((buyer.purchase_count, buyer.lifetime_value), (2, Decimal('100.00')))
        order.cancel(reason='test')
        order.save()
        buyer.refresh_from_db()
        self.assertEqual((buyer.purchase_count, buyer.lifetime_value), (1, Decimal('20.00')))
        order.save()  # a later save of the same order refreshes nothing more
        buyer.refresh_from_db()
        self.assertEqual(buyer.purchase_count, 1)


class CohortCurrencyTests(TestCase):
    def test_a_cohort_cell_sums_only_the_tables_currency(self):
        from plugins.installed.analytics.services_cohorts import _sum_revenue

        usd_buyer = get_user_model().objects.create_user(
            username='us', email='us@example.com', password='x'
        )
        mixed = get_user_model().objects.create_user(
            username='mx', email='mx@example.com', password='x'
        )
        _order(40, currency='USD', customer=usd_buyer)
        _order(30, currency='EUR', customer=mixed)
        _order(5, currency='USD', customer=mixed)
        start = (timezone.now() - timedelta(days=1)).date()
        end = (timezone.now() + timedelta(days=1)).date()
        # A cohort that bought only in USD has no euro revenue, not a relabelled 40.
        self.assertEqual(_sum_revenue([usd_buyer.pk], start, end, 'EUR'), Decimal('0'))
        # A mixed cohort's euro cell holds its euros only, whichever currency leads.
        self.assertEqual(_sum_revenue([mixed.pk], start, end, 'EUR'), Decimal('30.00'))
        self.assertEqual(_sum_revenue([mixed.pk], start, end, 'USD'), Decimal('5.00'))
