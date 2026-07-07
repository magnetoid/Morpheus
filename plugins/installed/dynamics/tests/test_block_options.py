"""Block options — B2 filters (price band, exclude purchased/ids, pin), B3
display (reason label + templatetag), B4 autopilot controls, and the edit-form
round-trip that lets merchants set them all."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.dynamics.models import DynamicBlock
from plugins.installed.dynamics.services import reason_label, recommend
from plugins.installed.orders.models import Order, OrderItem

Customer = get_user_model()


def _product(slug, *, price='20.00'):
    return Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal(price), 'USD'),
        status='active',
    )


def _block(**kw):
    kw.setdefault('name', 'B')
    kw.setdefault('slot', 'home_below_grid')
    kw.setdefault('strategy', 'manual')
    kw.setdefault('limit', 8)
    return DynamicBlock.objects.create(**kw)


class FilterOptionTests(TestCase):
    def test_price_band(self):
        _product('cheap', price='10.00')
        mid = _product('mid', price='20.00')
        _product('exp', price='40.00')
        b = _block(price_min=Decimal('15'), price_max=Decimal('25'))
        ids = [p.id for p in recommend(b, request=RequestFactory().get('/'))]
        self.assertEqual(ids, [mid.id])

    def test_excluded_ids_dropped(self):
        keep, drop = _product('keep'), _product('drop')
        b = _block(excluded_product_ids=[str(drop.id)])
        ids = [p.id for p in recommend(b, request=RequestFactory().get('/'))]
        self.assertIn(keep.id, ids)
        self.assertNotIn(drop.id, ids)

    def test_pinned_ids_first(self):
        old = _product('old')  # created first → normally last by -created_at
        _product('new')
        b = _block(pinned_product_ids=[str(old.id)])
        ids = [p.id for p in recommend(b, request=RequestFactory().get('/'))]
        self.assertEqual(ids[0], old.id)

    def test_exclude_purchased(self):
        bought, other = _product('bought'), _product('other')
        u = Customer.objects.create_user(username='u', email='u@x.io', password='pw')
        o = Order.objects.create(
            customer=u,
            email='b@x.io',
            subtotal=Money(Decimal('10'), 'USD'),
            total=Money(Decimal('10'), 'USD'),
        )
        Order.objects.filter(pk=o.pk).update(status='confirmed')
        OrderItem.objects.create(
            order=o,
            product=bought,
            product_name=bought.name,
            sku=bought.sku,
            quantity=1,
            unit_price=bought.price,
            total_price=bought.price,
        )
        b = _block(exclude_purchased=True)
        ids = [p.id for p in recommend(b, request=RequestFactory().get('/'), customer=u)]
        self.assertIn(other.id, ids)
        self.assertNotIn(bought.id, ids)


class DisplayOptionTests(TestCase):
    def test_reason_label(self):
        self.assertEqual(reason_label(_block(strategy='trending')), 'Trending now')
        self.assertEqual(reason_label(_block(strategy='on_sale')), 'On sale')
        self.assertEqual(reason_label(_block(strategy='manual')), 'Recommended for you')

    def test_templatetag_includes_reason_when_enabled(self):
        from plugins.installed.dynamics.templatetags.dynamics import dynamic_blocks_for

        _product('x')
        _block(strategy='new_arrivals', show_reason=True)
        rows = dynamic_blocks_for({'request': RequestFactory().get('/')}, 'home_below_grid')
        self.assertTrue(rows)
        self.assertEqual(rows[0]['reason'], 'New arrival')


class AutopilotControlTests(TestCase):
    def test_block_overrides_thread_without_crash(self):
        _product('p1')
        _product('p2')
        b = _block(
            strategy='autopilot',
            segment_override='mobile:evening:anon',
            exploration_rate=0.0,
            diversity_cap=2,
        )
        ids = [p.id for p in recommend(b, request=RequestFactory().get('/'))]
        self.assertGreaterEqual(len(ids), 1)


class EditFormTests(TestCase):
    def setUp(self):
        self.staff = Customer.objects.create_user(
            username='s', email='s@x.io', password='pw', is_staff=True
        )
        self.client.force_login(self.staff)

    def test_form_saves_all_option_fields(self):
        p = _product('pin')
        resp = self.client.post(
            '/dashboard/dynamics/new/',
            {
                'name': 'Opt block',
                'slot': 'home_below_grid',
                'strategy': 'autopilot',
                'limit': '8',
                'sort_order': '50',
                'enabled': 'on',
                'price_min': '5',
                'price_max': '50',
                'exclude_out_of_stock': 'on',
                'exclude_purchased': 'on',
                'pinned_product_ids': str(p.id),
                'layout': 'grid',
                'columns': '3',
                'show_price': 'on',
                'show_reason': 'on',
                'exploration_rate': '0.2',
                'diversity_cap': '5',
                'segment_override': 'desktop:morning:known',
            },
        )
        self.assertEqual(resp.status_code, 302)
        b = DynamicBlock.objects.get(name='Opt block')
        self.assertEqual(b.price_min, Decimal('5'))
        self.assertTrue(b.exclude_out_of_stock)
        self.assertTrue(b.exclude_purchased)
        self.assertEqual(b.layout, 'grid')
        self.assertEqual(b.columns, 3)
        self.assertTrue(b.show_reason)
        self.assertEqual(b.exploration_rate, 0.2)
        self.assertEqual(b.diversity_cap, 5)
        self.assertEqual(b.segment_override, 'desktop:morning:known')
        self.assertEqual(b.pinned_product_ids, [str(p.id)])
