"""CMS Pages dashboard — permission boundary + CRUD.

Covers the new editor/row-action views (urls_dashboard.py / dashboard.py).
The new-page GET also renders page_form.html, so a template syntax error
fails these tests too.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.cms.models import Page

User = get_user_model()

NEW_URL = '/dashboard/cms/pages/new/'
LIST_URL = '/dashboard/apps/cms/pages/'


class PageDashboardTests(TestCase):
    def setUp(self):
        self.page = Page.objects.create(
            title='About', slug='about', body='<p>Hello</p>', state='published'
        )

    def _staff(self):
        u = User.objects.create_user(username='adm', email='adm@example.com', password='x')
        u.is_staff = True
        u.save()
        self.client.force_login(u)
        return u

    # ── boundary ──────────────────────────────────────────────────────────
    def test_anonymous_blocked(self):
        self.assertEqual(self.client.get(NEW_URL).status_code, 302)

    def test_authed_without_scope_blocked(self):
        u = User.objects.create_user(username='joe', email='joe@example.com', password='x')
        self.client.force_login(u)
        self.assertEqual(self.client.get(NEW_URL).status_code, 302)

    def test_authed_with_scope_allowed(self):
        self._staff()
        r = self.client.get(NEW_URL)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data-richtext')  # richtext (Lexical) editor rendered
        self.assertContains(r, 'name="body"')  # the body field still submits

    # ── CRUD ──────────────────────────────────────────────────────────────
    def test_create_page(self):
        self._staff()
        r = self.client.post(
            NEW_URL,
            {
                'title': 'Terms',
                'slug': 'terms',
                'excerpt': 'Legal',
                'body': '<h2>Terms</h2><ul><li>One</li></ul>',
                'state': 'published',
                'layout': 'default',
                'publish_at': '',
            },
        )
        self.assertRedirects(r, LIST_URL, fetch_redirect_response=False)
        page = Page.objects.get(slug='terms')
        self.assertIn('<h2>Terms</h2>', page.body)  # body persisted through bleach

    def test_edit_page(self):
        self._staff()
        r = self.client.post(
            f'/dashboard/cms/pages/{self.page.id}/edit/',
            {
                'title': 'About us',
                'slug': 'about',
                'excerpt': '',
                'body': '<p>Updated</p>',
                'state': 'published',
                'layout': 'long_form',
                'publish_at': '',
            },
        )
        self.assertEqual(r.status_code, 302)
        self.page.refresh_from_db()
        self.assertEqual(self.page.title, 'About us')
        self.assertEqual(self.page.layout, 'long_form')

    def test_duplicate_page(self):
        self._staff()
        r = self.client.post(f'/dashboard/cms/pages/{self.page.id}/duplicate/')
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Page.objects.filter(slug='about-copy', state='draft').exists())

    def test_delete_page(self):
        self._staff()
        r = self.client.post(f'/dashboard/cms/pages/{self.page.id}/delete/')
        self.assertRedirects(r, LIST_URL, fetch_redirect_response=False)
        self.assertFalse(Page.objects.filter(slug='about').exists())

    def test_delete_is_post_only(self):
        self._staff()
        self.assertEqual(
            self.client.get(f'/dashboard/cms/pages/{self.page.id}/delete/').status_code, 405
        )

    def test_duplicate_slug_rejected(self):
        self._staff()
        r = self.client.post(
            NEW_URL,
            {
                'title': 'X',
                'slug': 'about',
                'body': '<p>x</p>',
                'state': 'draft',
                'layout': 'default',
            },
        )
        self.assertEqual(r.status_code, 200)  # re-renders form with error
        self.assertEqual(Page.objects.filter(slug='about').count(), 1)

    def test_pages_list_shows_hardcoded(self):
        # The list merges editable CMS pages with code-owned pages declared by
        # active plugins via contribute_hardcoded_pages() (storefront, etc.).
        self._staff()
        r = self.client.get(LIST_URL)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Managed in code')  # a locked hardcoded row rendered
        self.assertContains(r, '/checkout/')  # storefront's code-owned page
