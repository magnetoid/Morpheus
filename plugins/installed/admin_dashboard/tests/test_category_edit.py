"""Category edit dashboard view — permission boundary + save behaviour.

Mirrors the collection-edit flow: GET renders a prefilled form, a valid
POST persists the Category and redirects, and an invalid POST (duplicate
slug, or a self/descendant parent) re-renders the form with a field
error (HTTP 200, never a 500) without corrupting the row.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from plugins.installed.catalog.models import Category


class CategoryEditTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username='staff', email='staff@example.com', password='x', is_staff=True
        )
        self.shopper = User.objects.create_user(
            username='shopper', email='shopper@example.com', password='x', is_staff=False
        )
        self.root = Category.objects.create(name='Fiction', slug='fiction')
        self.child = Category.objects.create(name='Sci-Fi', slug='sci-fi', parent=self.root)
        self.other = Category.objects.create(name='Non-Fiction', slug='non-fiction')
        self.url = reverse('admin_dashboard:category_edit', kwargs={'category_id': self.root.id})

    # --- permission boundary -------------------------------------------------

    def test_url_reverses(self):
        self.assertEqual(self.url, f'/dashboard/categories/{self.root.id}/edit/')

    def test_anonymous_blocked(self):
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, (302, 403))
        if resp.status_code == 302:
            # staff_member_required bounces to the login page, never to the
            # edit view itself (the path only appears as the ?next= target).
            self.assertIn('login', resp.headers.get('Location', '') or '')

    def test_non_staff_blocked(self):
        self.client.force_login(self.shopper)
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, (302, 403))

    def test_staff_get_renders(self):
        self.client.force_login(self.staff)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Edit category')
        self.assertContains(resp, 'fiction')

    # --- successful save -----------------------------------------------------

    def test_staff_post_updates_category(self):
        self.client.force_login(self.staff)
        resp = self.client.post(
            self.url,
            {
                'name': 'Literary Fiction',
                'slug': 'fiction',
                'parent': '',
                'description': 'Updated blurb.',
                'is_active': 'on',
                'sort_order': '3',
                'meta_title': 'Literary Fiction',
                'meta_description': 'Best of literary fiction.',
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.root.refresh_from_db()
        self.assertEqual(self.root.name, 'Literary Fiction')
        self.assertEqual(self.root.description, 'Updated blurb.')
        self.assertEqual(self.root.sort_order, 3)

    def test_staff_post_can_reparent(self):
        self.client.force_login(self.staff)
        url = reverse('admin_dashboard:category_edit', kwargs={'category_id': self.child.id})
        resp = self.client.post(
            url,
            {
                'name': 'Sci-Fi',
                'slug': 'sci-fi',
                'parent': str(self.other.id),
                'description': '',
                'is_active': 'on',
                'sort_order': '0',
                'meta_title': '',
                'meta_description': '',
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.child.refresh_from_db()
        self.assertEqual(self.child.parent_id, self.other.id)

    # --- invalid save: must not 500, must not corrupt -----------------------

    def test_duplicate_slug_rejected(self):
        self.client.force_login(self.staff)
        resp = self.client.post(
            self.url,
            {
                'name': 'Fiction',
                'slug': 'non-fiction',  # already owned by self.other
                'parent': '',
                'description': '',
                'is_active': 'on',
                'sort_order': '0',
                'meta_title': '',
                'meta_description': '',
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'already in use')
        self.root.refresh_from_db()
        self.assertEqual(self.root.slug, 'fiction')  # unchanged

    def test_self_parent_rejected(self):
        self.client.force_login(self.staff)
        resp = self.client.post(
            self.url,
            {
                'name': 'Fiction',
                'slug': 'fiction',
                'parent': str(self.root.id),  # itself
                'description': '',
                'is_active': 'on',
                'sort_order': '0',
                'meta_title': '',
                'meta_description': '',
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.root.refresh_from_db()
        self.assertIsNone(self.root.parent_id)  # unchanged / not corrupted

    def test_descendant_parent_rejected(self):
        # Making 'Fiction' a child of its own child 'Sci-Fi' would cycle.
        self.client.force_login(self.staff)
        resp = self.client.post(
            self.url,
            {
                'name': 'Fiction',
                'slug': 'fiction',
                'parent': str(self.child.id),  # a descendant
                'description': '',
                'is_active': 'on',
                'sort_order': '0',
                'meta_title': '',
                'meta_description': '',
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.root.refresh_from_db()
        self.assertIsNone(self.root.parent_id)


class CategoryCreateTests(TestCase):
    """ "New category" is a dashboard page. It once linked to Django's stock
    admin (/admin/catalog/category/add/), which is mounted only under DEBUG,
    so the button 404'd on every live store."""

    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='staff', email='staff@example.com', password='x', is_staff=True
        )
        self.url = reverse('admin_dashboard:category_new')

    def test_url_reverses(self):
        self.assertEqual(self.url, '/dashboard/categories/new/')

    def test_non_staff_blocked(self):
        shopper = get_user_model().objects.create_user(
            username='shopper', email='shopper@example.com', password='x'
        )
        self.client.force_login(shopper)
        self.assertIn(self.client.get(self.url).status_code, (302, 403))

    def test_staff_get_renders_an_empty_form(self):
        self.client.force_login(self.staff)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'New category')
        self.assertContains(resp, 'Create category')
        self.assertNotContains(resp, 'View on storefront')

    def test_staff_post_creates_a_category_with_a_slug_from_its_name(self):
        parent = Category.objects.create(name='Gear', slug='gear')
        self.client.force_login(self.staff)
        resp = self.client.post(
            self.url,
            {
                'name': 'Water Filters',
                'slug': '',
                'parent': str(parent.pk),
                'description': 'Clean water anywhere.',
                'is_active': 'on',
                'sort_order': '0',
            },
        )
        created = Category.objects.get(name='Water Filters')
        self.assertRedirects(
            resp,
            reverse('admin_dashboard:category_edit', kwargs={'category_id': created.id}),
            fetch_redirect_response=False,
        )
        self.assertEqual((created.slug, created.parent_id), ('water-filters', parent.pk))

    def test_a_duplicate_slug_re_renders_the_form(self):
        Category.objects.create(name='Radios', slug='radios')
        self.client.force_login(self.staff)
        resp = self.client.post(self.url, {'name': 'Radios', 'slug': '', 'sort_order': '0'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'That slug is already in use')
        self.assertEqual(Category.objects.filter(slug='radios').count(), 1)

    def test_the_list_links_to_the_dashboard_page(self):
        self.client.force_login(self.staff)
        for categories in (False, True):  # the empty state, then the table header
            if categories:
                Category.objects.create(name='Tools', slug='tools')
            resp = self.client.get(reverse('admin_dashboard:categories'))
            self.assertContains(resp, 'href="/dashboard/categories/new/"')
            self.assertNotContains(resp, '/admin/catalog/')


class NoStockAdminLinkTests(TestCase):
    """Django's stock admin is mounted only under DEBUG (morph/urls.py), so a
    dashboard link into it is a 404 on every live store."""

    def test_no_dashboard_template_links_into_the_stock_admin(self):
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / 'templates'
        pattern = re.compile(r"""(?:href|action|action_url)=["']/admin/(?!login)""")
        offenders = [
            str(path.relative_to(root))
            for path in root.rglob('*.html')
            if pattern.search(path.read_text(encoding='utf-8'))
        ]
        self.assertEqual(offenders, [])
