"""CMS Menus dashboard — permission boundary + CRUD + storefront wiring.

Covers the menu-builder views (urls_dashboard.py / dashboard.py menu_edit),
the get_menu() kind round-trip the theme renders from, and the seeder.
A template syntax error in menu_form.html fails the staff GET test too.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from plugins.installed.cms.models import Menu, MenuItem
from plugins.installed.cms.services import get_menu

User = get_user_model()

NEW_URL = '/dashboard/cms/menus/new/'


class MenuDashboardBoundaryTests(TestCase):
    def setUp(self):
        self.menu = Menu.objects.create(key='header', label='Header')

    def _staff(self):
        u = User.objects.create_user(username='adm', email='adm@example.com', password='x')
        u.is_staff = True
        u.save()
        self.client.force_login(u)
        return u

    def test_anonymous_blocked(self):
        self.assertEqual(self.client.get(NEW_URL).status_code, 302)

    def test_authed_without_scope_blocked(self):
        u = User.objects.create_user(username='joe', email='joe@example.com', password='x')
        self.client.force_login(u)
        self.assertEqual(self.client.get(NEW_URL).status_code, 302)

    def test_authed_with_scope_allowed(self):
        self._staff()
        self.assertEqual(self.client.get(NEW_URL).status_code, 200)
        self.assertEqual(
            self.client.get(f'/dashboard/cms/menus/{self.menu.id}/edit/').status_code, 200
        )


class MenuCrudTests(TestCase):
    def setUp(self):
        u = User.objects.create_user(username='adm', email='adm@example.com', password='x')
        u.is_staff = True
        u.save()
        self.client.force_login(u)
        self.menu = Menu.objects.create(key='header', label='Header')
        self.url = f'/dashboard/cms/menus/{self.menu.id}/edit/'

    def test_add_item(self):
        self.client.post(
            self.url,
            {'action': 'add_item', 'item_label': 'Staff picks', 'item_url': '/staff-picks/'},
        )
        item = self.menu.items.get()
        self.assertEqual(item.label, 'Staff picks')
        self.assertEqual(item.kind, MenuItem.KIND_LINK)

    def test_add_mega_item_kind_persists(self):
        self.client.post(
            self.url,
            {'action': 'add_item', 'item_label': 'Genres', 'item_kind': 'mega_categories'},
        )
        self.assertEqual(self.menu.items.get().kind, 'mega_categories')

    def test_delete_item(self):
        item = MenuItem.objects.create(menu=self.menu, label='Gone', url='/x/')
        self.client.post(self.url, {'action': 'delete_item', 'item_id': str(item.id)})
        self.assertFalse(self.menu.items.exists())

    def test_move_item_reorders(self):
        a = MenuItem.objects.create(menu=self.menu, label='A', url='/a/', order=10)
        b = MenuItem.objects.create(menu=self.menu, label='B', url='/b/', order=20)
        self.client.post(self.url, {'action': 'move_item', 'item_id': str(b.id), 'direction': 'up'})
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertLess(b.order, a.order)


class GetMenuTests(TestCase):
    def test_get_menu_exposes_kind(self):
        menu = Menu.objects.create(key='header', label='Header')
        MenuItem.objects.create(menu=menu, label='Genres', kind='mega_categories', order=10)
        MenuItem.objects.create(menu=menu, label='Journal', url='/journal/', order=20)
        data = get_menu('header')
        kinds = [i['kind'] for i in data['items']]
        self.assertEqual(kinds, ['mega_categories', 'link'])

    def test_inactive_menu_returns_none(self):
        Menu.objects.create(key='hidden', label='Hidden', is_active=False)
        self.assertIsNone(get_menu('hidden'))


class SeedNavMenusTests(TestCase):
    def test_seed_is_idempotent_and_populates(self):
        call_command('seed_nav_menus')
        header = get_menu('header')
        self.assertIsNotNone(header)
        self.assertTrue(any(i['kind'] == 'mega_categories' for i in header['items']))
        count = Menu.objects.get(key='header').items.count()
        # Re-run must not duplicate items.
        call_command('seed_nav_menus')
        self.assertEqual(Menu.objects.get(key='header').items.count(), count)
