"""dynamic_products — permission boundary + engine unit tests."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from djmoney.money import Money

from plugins.installed.catalog.models import Category, Product
from plugins.installed.dynamic_products.models import DynamicBlock
from plugins.installed.dynamic_products.services import recommend
from plugins.installed.orders.models import Order, OrderItem

Customer = get_user_model()


def _product(slug, *, category=None, featured=False, tags=None):
    p = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('10.00'), 'USD'),
        status='active',
        category=category,
        is_featured=featured,
    )
    if tags:
        p.tags.add(*tags)
    return p


def _paid_order(customer, products, *, status='confirmed'):
    order = Order.objects.create(
        customer=customer,
        email=getattr(customer, 'email', 'guest@example.com'),
        subtotal=Money(Decimal('10.00'), 'USD'),
        total=Money(Decimal('10.00'), 'USD'),
    )
    # status is a protected FSMField — set the initial paid state via update().
    Order.objects.filter(pk=order.pk).update(status=status)
    for p in products:
        OrderItem.objects.create(
            order=order,
            product=p,
            product_name=p.name,
            sku=p.sku,
            quantity=1,
            unit_price=p.price,
            total_price=p.price,
        )
    return order


# ---------------------------------------------------------------------------
# Permission boundary tests — the staff dashboard config view.
# ---------------------------------------------------------------------------


class DynamicProductsIndexBoundaryTests(TestCase):
    """anon blocked · non-staff blocked · staff allowed (customers.Customer)."""

    @classmethod
    def setUpTestData(cls):
        cls.url = reverse('dynamic_products:index')
        cls.shopper = Customer.objects.create_user(
            username='shopper', email='shopper@example.com', password='pw'
        )
        cls.staff = Customer.objects.create_user(
            username='staff', email='staff@example.com', password='pw', is_staff=True
        )

    def test_anonymous_redirected_to_login(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.headers['Location'])

    def test_authed_without_scope_blocked(self):
        self.client.force_login(self.shopper)
        resp = self.client.get(self.url)
        # staff_member_required bounces non-staff to the admin login.
        self.assertIn(resp.status_code, (302, 403))

    def test_authed_staff_allowed(self):
        self.client.force_login(self.staff)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# Engine unit tests — each strategy returns sane results.
# ---------------------------------------------------------------------------


class DynamicProductsEngineTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.cat = Category.objects.create(name='Fiction', slug='fiction')
        self.other_cat = Category.objects.create(name='Cooking', slug='cooking')

    def _request(self, *, user=None, session=None):
        req = self.rf.get('/')
        req.user = user or _Anon()
        req.session = session if session is not None else {}
        return req

    def test_manual_filters_by_category(self):
        in_cat = _product('a', category=self.cat)
        _product('b', category=self.other_cat)
        block = DynamicBlock.objects.create(name='M', slot='home_below_grid', strategy='manual')
        block.categories.add(self.cat)

        out = recommend(block, request=self._request(), customer=None)
        self.assertEqual([p.pk for p in out], [in_cat.pk])

    def test_manual_filters_by_tag(self):
        tagged = _product('sale1', tags=['sale'])
        _product('full', tags=['new'])
        block = DynamicBlock.objects.create(
            name='T', slot='home_below_grid', strategy='manual', tags=['sale']
        )
        out = recommend(block, request=self._request(), customer=None)
        self.assertEqual([p.pk for p in out], [tagged.pk])

    def test_recently_viewed_reads_session(self):
        p1 = _product('seen1')
        p2 = _product('seen2')
        session = {'recently_viewed': ['seen2', 'seen1']}
        block = DynamicBlock.objects.create(
            name='RV', slot='home_below_grid', strategy='recently_viewed'
        )
        out = recommend(block, request=self._request(session=session), customer=None)
        # Order preserved from the session list (freshest first).
        self.assertEqual([p.pk for p in out], [p2.pk, p1.pk])

    def test_related_uses_same_category(self):
        anchor = _product('anchor', category=self.cat)
        sibling = _product('sibling', category=self.cat)
        _product('stranger', category=self.other_cat)
        block = DynamicBlock.objects.create(name='R', slot='pdp_below_form', strategy='related')
        out = recommend(block, request=self._request(), customer=None, context_product=anchor)
        ids = [p.pk for p in out]
        self.assertIn(sibling.pk, ids)
        self.assertNotIn(anchor.pk, ids)

    def test_bought_together_from_orders(self):
        anchor = _product('anchor')
        partner = _product('partner')
        buyer = Customer.objects.create_user(email='b@example.com', password='pw')
        _paid_order(buyer, [anchor, partner])
        block = DynamicBlock.objects.create(
            name='BT', slot='pdp_below_form', strategy='bought_together'
        )
        out = recommend(block, request=self._request(), customer=None, context_product=anchor)
        ids = [p.pk for p in out]
        self.assertIn(partner.pk, ids)
        self.assertNotIn(anchor.pk, ids)

    def test_pdp_only_strategy_empty_without_context(self):
        _product('x', category=self.cat)
        block = DynamicBlock.objects.create(name='R', slot='pdp_below_form', strategy='related')
        # No context_product → related returns nothing (caller-side guard
        # lives in the template tag; the engine itself also yields []).
        out = recommend(block, request=self._request(), customer=None, context_product=None)
        self.assertEqual(out, [])

    def test_for_you_excludes_purchased(self):
        bought = _product('bought', category=self.cat)
        fresh = _product('fresh', category=self.cat)
        buyer = Customer.objects.create_user(email='fy@example.com', password='pw')
        # Buyer purchased `bought` and viewed something in the same category.
        _paid_order(buyer, [bought])
        block = DynamicBlock.objects.create(name='FY', slot='home_above_grid', strategy='for_you')

        req = self._request(user=buyer, session={'recently_viewed': ['fresh']})
        out = recommend(block, request=req, customer=buyer, context_product=None)
        ids = [p.pk for p in out]
        self.assertNotIn(bought.pk, ids)  # already purchased → excluded
        self.assertIn(fresh.pk, ids)  # affinity / recently-viewed → surfaced

    def test_for_you_anonymous_fallback_not_empty(self):
        # Cold-start anonymous visitor: no history at all. Falls back to
        # featured/recent catalog so the block still renders.
        _product('pop1', featured=True)
        _product('pop2', featured=True)
        block = DynamicBlock.objects.create(name='FY', slot='home_above_grid', strategy='for_you')
        out = recommend(block, request=self._request(), customer=None)
        self.assertGreaterEqual(len(out), 1)

    def test_limit_is_respected(self):
        for i in range(6):
            _product(f'p{i}', featured=True)
        block = DynamicBlock.objects.create(
            name='L', slot='home_below_grid', strategy='manual', limit=3
        )
        out = recommend(block, request=self._request(), customer=None)
        self.assertEqual(len(out), 3)

    def test_recommend_never_raises(self):
        # Even a nonsense strategy falls through to for_you and returns a list.
        block = DynamicBlock.objects.create(name='Bad', slot='home_below_grid', strategy='manual')
        block.strategy = 'does_not_exist'
        out = recommend(block, request=self._request(), customer=None)
        self.assertIsInstance(out, list)


class _Anon:
    """Minimal AnonymousUser stand-in for the engine's is_authenticated check."""

    is_authenticated = False
