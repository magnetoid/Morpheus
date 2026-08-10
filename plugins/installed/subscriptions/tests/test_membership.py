"""Bookstore membership — discount helper, cart-discount hook, storefront page."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.subscriptions.membership import (
    apply_member_discount,
    member_discount_percent,
)
from plugins.installed.subscriptions.models import Plan, Subscription


def _plan(discount=20, **kw):
    defaults = {
        'name': 'Member',
        'slug': 'member',
        'price': Money(5, 'USD'),
        'member_discount_percent': discount,
    }
    defaults.update(kw)
    return Plan.objects.create(**defaults)


def _paid_sub(customer, plan, state='active'):
    """A subscription with EVIDENCE OF PAYMENT.

    `member_discount_percent` requires proof the plan was paid for, not just an
    entitling state — a bare `state='active'` row is exactly what the old
    unpaid signup path minted and must NOT entitle (see test_entitlement.py).
    A provider subscription id is the cheapest realistic evidence: it means
    Stripe holds a verified card.
    """
    return Subscription.objects.create(
        customer=customer, plan=plan, state=state, provider_subscription_id='sub_test'
    )


def _breakdown(subtotal='100.00'):
    z = Money(Decimal('0'), 'USD')
    sub = Money(Decimal(subtotal), 'USD')
    return {
        'currency': 'USD',
        'subtotal': sub,
        'shipping': z,
        'tax': z,
        'discount': z,
        'total': sub,
        'meta': {},
    }


class MemberDiscountHelperTests(TestCase):
    def setUp(self):
        self.cust = get_user_model().objects.create_user(
            username='m', email='m@x.test', password='pw'
        )

    def test_zero_for_non_subscriber(self):
        self.assertEqual(member_discount_percent(self.cust), 0)

    def test_best_active_discount(self):
        _paid_sub(self.cust, _plan(15, slug='a'))
        _paid_sub(self.cust, _plan(25, slug='b'))
        self.assertEqual(member_discount_percent(self.cust), 25)

    def test_cancelled_subscription_ignored(self):
        _paid_sub(self.cust, _plan(30, slug='c'), state='cancelled')
        self.assertEqual(member_discount_percent(self.cust), 0)


class CartDiscountHookTests(TestCase):
    def setUp(self):
        self.cust = get_user_model().objects.create_user(
            username='m', email='m@x.test', password='pw'
        )

    def test_applies_member_discount(self):
        _paid_sub(self.cust, _plan(20))
        out = apply_member_discount(_breakdown('100.00'), customer=self.cust)
        self.assertEqual(out['discount'], Money(Decimal('20.00'), 'USD'))
        self.assertEqual(out['total'], Money(Decimal('80.00'), 'USD'))
        self.assertEqual(out['meta']['member_discount_percent'], 20)

    def test_no_discount_for_non_member(self):
        out = apply_member_discount(_breakdown('100.00'), customer=self.cust)
        self.assertEqual(out['total'], Money(Decimal('100.00'), 'USD'))
        self.assertNotIn('member_discount_percent', out['meta'])

    def test_stacks_on_existing_discount(self):
        _paid_sub(self.cust, _plan(10))
        bd = _breakdown('100.00')
        bd['discount'] = Money(Decimal('5.00'), 'USD')  # e.g. a coupon
        bd['total'] = Money(Decimal('95.00'), 'USD')
        out = apply_member_discount(bd, customer=self.cust)
        self.assertEqual(out['discount'], Money(Decimal('15.00'), 'USD'))  # 5 + 10
        self.assertEqual(out['total'], Money(Decimal('85.00'), 'USD'))


class MembershipPageTests(TestCase):
    def test_page_lists_active_plans(self):
        _plan(20, name='Gold')
        r = Client().get('/membership/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Gold')
        self.assertContains(r, '20% off')

    def test_subscribe_requires_login(self):
        plan = _plan()
        r = Client().post('/membership/subscribe/', {'plan_id': str(plan.id)})
        self.assertEqual(r.status_code, 302)  # redirect to login

    def test_logged_in_subscribe_creates_free_membership(self):
        # A FREE plan activates immediately — there is nothing to charge.
        plan = _plan(price=Money(0, 'USD'))
        c = Client()
        cust = get_user_model().objects.create_user(username='j', email='j@x.test', password='pw')
        c.force_login(cust)
        c.post('/membership/subscribe/', {'plan_id': str(plan.id)})
        self.assertTrue(Subscription.objects.filter(customer=cust, state='active').exists())

    def test_logged_in_subscribe_refuses_a_paid_plan(self):
        # This path has no payment leg, so it must not hand out a paid
        # membership. It used to create state='active' unconditionally.
        plan = _plan()  # $5/mo
        c = Client()
        cust = get_user_model().objects.create_user(username='k', email='k@x.test', password='pw')
        c.force_login(cust)
        c.post('/membership/subscribe/', {'plan_id': str(plan.id)})
        self.assertFalse(Subscription.objects.filter(customer=cust).exists())


class PlanManagementTests(TestCase):
    def setUp(self):
        self.c = Client()
        self.c.force_login(
            get_user_model().objects.create_user(
                username='s', email='s@x.test', password='pw', is_staff=True
            )
        )

    def test_create_plan_with_discount(self):
        self.c.post(
            '/dashboard/subscriptions/',
            {
                'action': 'create_plan',
                'name': 'Book Club',
                'price': '9.99',
                'interval': 'month',
                'member_discount_percent': '15',
            },
        )
        plan = Plan.objects.get(name='Book Club')
        self.assertEqual(plan.member_discount_percent, 15)
        self.assertEqual(plan.slug, 'book-club')

    def test_update_plan_discount_clamped(self):
        plan = _plan(10)
        self.c.post(
            '/dashboard/subscriptions/',
            {
                'action': 'update_plan',
                'plan_id': str(plan.id),
                'member_discount_percent': '250',
                'is_active': 'on',
            },
        )
        plan.refresh_from_db()
        self.assertEqual(plan.member_discount_percent, 100)  # clamped to 100
