"""A category's long description: the buying and planning guide below its products.

A category had one plain-text description, shown as the short intro above the
products and used as the meta description, so there was nowhere for real content.
The long description is formatted text (the product editor's), shown below the
grid on every theme, cleaned of unsafe HTML on save whoever writes it: the
dashboard, Linda or the API.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.catalog.models import Category


class CategoryLongDescriptionTests(TestCase):
    def test_saving_keeps_formatting_and_drops_unsafe_html(self):
        Category.objects.create(
            name='Water',
            slug='water',
            long_description=(
                '<h2>How to choose</h2><p>Plan <strong>4 liters</strong> a day.</p>'
                '<script>alert(1)</script><a href="javascript:alert(1)">x</a>'
            ),
        )
        html = Category.objects.get(slug='water').long_description
        self.assertIn('<h2>How to choose</h2>', html)
        self.assertIn('<strong>4 liters</strong>', html)
        self.assertNotIn('<script', html)
        self.assertNotIn('javascript:', html)

    def test_linda_can_write_it(self):
        from plugins.installed.agent_core.tools.catalog import update_category_tool

        Category.objects.create(name='Water', slug='water')
        update_category_tool.handler(slug='water', long_description='<p>Guide.</p>')
        self.assertEqual(Category.objects.get(slug='water').long_description, '<p>Guide.</p>')

    def test_the_api_exposes_it(self):
        from plugins.installed.catalog.graphql.types import CategoryType

        self.assertIn('long_description', CategoryType.__annotations__)

    def test_the_dashboard_form_saves_it(self):
        owner = get_user_model().objects.create_superuser('boss', 'boss@example.com', 'x')
        cat = Category.objects.create(name='Water', slug='water')
        self.client.force_login(owner)
        edit = f'/dashboard/categories/{cat.pk}/edit/'
        page = self.client.get(edit)
        self.assertContains(page, 'name="long_description"')
        self.client.post(
            edit,
            {
                'name': 'Water',
                'slug': 'water',
                'description': 'Short intro.',
                'long_description': '<h2>Guide</h2><p>Body.</p>',
                'is_active': 'on',
                'sort_order': '0',
            },
        )
        cat.refresh_from_db()
        self.assertEqual(cat.description, 'Short intro.')
        self.assertEqual(cat.long_description, '<h2>Guide</h2><p>Body.</p>')
