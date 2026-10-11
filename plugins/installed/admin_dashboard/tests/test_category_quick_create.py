"""Categories made from the product form's category picker (owner, 2026-10-11).

The owner asked for a styled category and subcategory dropdown on the product
editor that can also add a new category on the spot. The picker posts to one
JSON endpoint; a category made there must be exactly what the Categories page
would make, and typing a name that already exists under the same parent must
pick that category rather than mint a twin.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

URL = '/dashboard/categories/quick-create/'


class CategoryQuickCreateTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='cat-staff', email='cat@x.test', password='x', is_staff=True,
            is_superuser=True,
        )  # fmt: skip
        self.client = Client()
        self.client.force_login(staff)

    def _post(self, **data):
        return self.client.post(URL, data)

    def test_a_top_level_category_is_created(self):
        from plugins.installed.catalog.models import Category

        data = self._post(name='Water storage').json()
        self.assertTrue(data['ok'])
        category = Category.objects.get(pk=data['id'])
        self.assertEqual(category.name, 'Water storage')
        self.assertEqual(category.slug, 'water-storage')
        self.assertTrue(category.is_active)
        self.assertIsNone(category.parent_id)
        self.assertEqual((data['depth'], data['path'], data['parent_id']), (0, 'Water storage', ''))

    def test_a_subcategory_lands_under_its_parent(self):
        parent = self._post(name='Aromatherapy').json()
        data = self._post(name='Essential oils', parent=parent['id']).json()
        self.assertEqual(data['parent_id'], parent['id'])
        self.assertEqual(data['depth'], 1)
        self.assertEqual(data['path'], 'Aromatherapy › Essential oils')

    def test_the_same_name_under_the_same_parent_picks_the_existing_category(self):
        from plugins.installed.catalog.models import Category

        first = self._post(name='Teas').json()
        again = self._post(name='  teas ').json()
        self.assertTrue(again['ok'])
        self.assertEqual(again['id'], first['id'])
        self.assertTrue(again['existing'])
        self.assertEqual(Category.objects.filter(name__iexact='teas').count(), 1)

    def test_a_name_used_under_another_parent_gets_its_own_slug(self):
        from plugins.installed.catalog.models import Category

        pantry = self._post(name='Pantry').json()
        aroma = self._post(name='Aromatherapy').json()
        one = self._post(name='Oils', parent=pantry['id']).json()
        two = self._post(name='Oils', parent=aroma['id']).json()
        self.assertTrue(one['ok'] and two['ok'])
        self.assertNotEqual(one['id'], two['id'])
        slugs = set(Category.objects.filter(name='Oils').values_list('slug', flat=True))
        self.assertEqual(slugs, {'oils', 'oils-2'})

    def test_a_blank_name_is_refused_in_json(self):
        response = self._post(name='   ')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])
        self.assertTrue(response.json()['error'])

    def test_an_unknown_parent_is_refused_in_json(self):
        response = self._post(name='Lanterns', parent='00000000-0000-0000-0000-000000000000')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])

    def test_only_a_post_creates(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 405)
        self.assertFalse(response.json()['ok'])

    def test_a_visitor_cannot_create(self):
        from plugins.installed.catalog.models import Category

        response = Client().post(URL, {'name': 'Sneaky'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Category.objects.filter(name='Sneaky').exists())


class ProductFormPickerTests(TestCase):
    def test_the_product_form_wires_the_picker(self):
        from plugins.installed.catalog.models import Category

        top = Category.objects.create(name='Mushrooms', slug='mushrooms', is_active=True)
        Category.objects.create(name='Capsules', slug='capsules', parent=top, is_active=True)
        staff = get_user_model().objects.create_user(
            username='form-staff', email='form@x.test', password='x', is_staff=True,
            is_superuser=True,
        )  # fmt: skip
        client = Client()
        client.force_login(staff)
        html = client.get('/dashboard/products/new/').content.decode()
        self.assertIn('data-category-picker="single"', html)
        self.assertIn('data-category-picker="multi"', html)
        self.assertIn(f'data-create-url="{URL}"', html)
        self.assertIn('data-name="Capsules" data-depth="1"', html)
        self.assertIn('admin_dashboard/category-picker.js', html)
