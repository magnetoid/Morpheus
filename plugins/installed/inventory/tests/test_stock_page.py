"""The Stock page (Products → Inventory → Stock): stock across products, one
count box per row, written through ``InventoryService.set_quantity``."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase

from plugins.installed.admin_dashboard import navigation
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, StockMovement, Warehouse
from plugins.installed.inventory.services import low_stock_levels
from plugins.registry import app_registry

URL = '/dashboard/apps/inventory/stock/'


def _user(name, *, staff=True, superuser=False):
    return get_user_model().objects.create_user(
        username=name,
        email=f'{name}@example.test',
        password='x',
        is_staff=staff,
        is_superuser=superuser,
    )


def _variant(slug, *, tracked=True, name='Default'):
    product = Product.objects.create(
        name=slug.title(), slug=slug, sku=slug.upper(), price=5, track_inventory=tracked
    )
    return ProductVariant.objects.create(product=product, name=name, sku=slug.upper())


class _Base(TestCase):
    def setUp(self):
        self.client.force_login(_user('owner'))
        self.main = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        self.closed = Warehouse.objects.create(name='Closed', code='OLD', is_active=False)

    def level(self, slug, quantity, *, reserved=0, warehouse=None, tracked=True):
        return StockLevel.objects.create(
            variant=_variant(slug, tracked=tracked),
            warehouse=warehouse or self.main,
            quantity=quantity,
            reserved_quantity=reserved,
        )


class StockListTests(_Base):
    def test_lists_counted_stock(self):
        self.level('lantern', 14)
        self.level('hidden', 3, warehouse=self.closed)
        self.level('poster', 8, tracked=False)
        page = self.client.get(URL).content.decode()
        self.assertIn('Lantern', page)
        self.assertIn('LANTERN', page)
        self.assertIn('value="14"', page)
        self.assertIn('Main', page)
        self.assertNotIn('Hidden', page)
        self.assertNotIn('Poster', page)

    def test_status_filter(self):
        with patch('plugins.installed.inventory.services.low_stock_threshold', return_value=5):
            self.level('none', 0)
            self.level('few', 3)
            self.level('many', 9)
            out = self.client.get(URL, {'status': 'out'}).content.decode()
            low = self.client.get(URL, {'status': 'low'}).content.decode()
        self.assertIn('None', out)
        self.assertNotIn('Few', out)
        self.assertNotIn('Many', out)
        self.assertIn('None', low)
        self.assertIn('Few', low)
        self.assertNotIn('Many', low)
        page = self.client.get(URL).content.decode()
        self.assertIn('>Out<', page)
        self.assertIn('>Low<', page)

    def test_one_low_rule(self):
        self.level('none', 0)
        self.level('few', 3)
        self.level('many', 90)

        resp = self.client.get(URL, {'status': 'low'})
        listed = {row.pk for row in resp.context['page_obj']}
        self.assertEqual(listed, {sl.pk for sl in low_stock_levels()})
        self.assertNotIn(
            'id="low-stock"', self.client.get('/dashboard/inventory/warehouses/').content.decode()
        )
        from plugins.installed.ai_assistant.services import pulse

        self.assertEqual(pulse._low_stock_signal()['suggested_action']['url'], URL + '?status=low')
        home = self.client.get('/dashboard/').content.decode()
        self.assertIn(f'href="{URL}?status=low"', home)

    def test_search(self):
        self.level('lantern', 4)
        self.level('rope', 4)
        by_sku = self.client.get(URL, {'q': 'lanTERN'}).content.decode()
        self.assertIn('Lantern', by_sku)
        self.assertNotIn('Rope', by_sku)
        by_name = self.client.get(URL, {'q': 'ant'}).content.decode()
        self.assertIn('Lantern', by_name)
        none = self.client.get(URL, {'q': 'zzz'}).content.decode()
        self.assertIn('data-empty="stock"', none)

    def test_empty_store(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-empty="stock"', response.content.decode())

    def test_the_default_variant_name_is_hidden_and_a_real_one_shown(self):
        StockLevel.objects.create(variant=_variant('plain'), warehouse=self.main, quantity=1)
        StockLevel.objects.create(
            variant=_variant('shirt', name='Blue / L'), warehouse=self.main, quantity=1
        )
        page = self.client.get(URL).content.decode()
        self.assertNotIn('Default ·', page)
        self.assertIn('Blue / L', page)


class SetOnHandTests(_Base):
    def test_set_on_hand(self):
        sl = self.level('lantern', 4)
        response = self.client.post(
            URL + '?status=low&q=lan', {'level': str(sl.pk), 'quantity': '12'}
        )
        sl.refresh_from_db()
        self.assertEqual(sl.quantity, 12)
        self.assertEqual(StockMovement.objects.filter(stock_level=sl).count(), 1)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], URL + '?status=low&q=lan')

    def test_refuses_bad_counts(self):
        sl = self.level('lantern', 4)
        closed = self.level('hidden', 4, warehouse=self.closed)
        for level, quantity in (
            (sl, '-1'),
            (sl, ''),
            (sl, '2.5'),
            (sl, 'abc'),
            (closed, '9'),
        ):
            with self.subTest(quantity=quantity, level=level.pk):
                response = self.client.post(
                    URL, {'level': str(level.pk), 'quantity': quantity}, follow=True
                )
                level.refresh_from_db()
                self.assertEqual(level.quantity, 4)
                self.assertTrue([str(m) for m in response.context['messages']])
        self.assertEqual(StockMovement.objects.count(), 0)


class StockBoundaryTests(_Base):
    def test_boundaries(self):
        sl = self.level('lantern', 4)
        anon = Client()
        response = anon.get(URL)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])
        anon.post(URL, {'level': str(sl.pk), 'quantity': '99'})
        sl.refresh_from_db()
        self.assertEqual(sl.quantity, 4)
        clerk = Client()
        clerk.force_login(_user('clerk'))
        with (
            patch('core.authz.enforcement_mode', return_value='enforce'),
            patch('core.authz.has_capability', return_value=False),
        ):
            self.assertEqual(
                clerk.post(URL, {'level': str(sl.pk), 'quantity': '99'}).status_code, 403
            )
        sl.refresh_from_db()
        self.assertEqual(sl.quantity, 4)


class StockTabGroupTests(_Base):
    def test_tab_group(self):
        owner = get_user_model().objects.get(username='owner')
        owner.is_superuser = True
        owner.save()
        request = RequestFactory().get(URL)
        request.user = owner
        nav = navigation.build(request)
        self.assertEqual(nav['section'], 'products')
        self.assertEqual([t['label'] for t in nav['tabs']].count('Inventory'), 1)
        self.assertEqual([t['label'] for t in nav['subtabs']], ['Stock', 'Forecast'])
        app_registry.deactivate('inventory')
        self.addCleanup(app_registry.activate, 'inventory')
        labels = [t.label for t in navigation.tabs(owner)]
        self.assertNotIn('Stock', labels)
        self.assertNotIn('Forecast', labels)
