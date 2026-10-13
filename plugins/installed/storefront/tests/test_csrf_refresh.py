"""A form on an edge-cached storefront page still posts.

Montenegro's pages are cached by the CDN (public, s-maxage=60), so a cached page
carries the CSRF token of whoever filled the cache and sets no cookie: a new
visitor's "Accept all" on the cookie banner, and every other form on that page,
answered 403 (2026-10-13). A never-cached /csrf/ hands the visitor their own
cookie, and a script contributed to global_head writes it into every form.
"""

from __future__ import annotations

from django.test import Client, TestCase


class CsrfRefreshTests(TestCase):
    def test_the_endpoint_sets_the_visitors_cookie_and_is_never_cached(self):
        c = Client(enforce_csrf_checks=True)
        resp = c.get('/csrf/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('csrftoken', resp.cookies)
        self.assertTrue(resp.json()['token'])
        self.assertIn('no-store', resp['Cache-Control'])

    def test_it_is_not_repeated_under_a_language_prefix(self):
        from django.urls import Resolver404, resolve

        with self.assertRaises(Resolver404):
            resolve('/sr/csrf/')

    def test_a_post_with_the_cookie_value_as_its_token_is_accepted(self):
        # What the script does: the cookie's value goes into the form's token.
        c = Client(enforce_csrf_checks=True)
        c.get('/csrf/')
        token = c.cookies['csrftoken'].value
        resp = c.post('/consent/save/', {'csrfmiddlewaretoken': token, 'action': 'accept_all'})
        self.assertNotEqual(resp.status_code, 403)

    def test_a_post_with_a_cached_pages_token_is_what_fails(self):
        # The bug: a token minted for someone else.
        other = Client(enforce_csrf_checks=True)
        other.get('/csrf/')
        stale = other.cookies['csrftoken'].value
        visitor = Client(enforce_csrf_checks=True)
        visitor.get('/csrf/')
        resp = visitor.post(
            '/consent/save/', {'csrfmiddlewaretoken': stale, 'action': 'accept_all'}
        )
        self.assertEqual(resp.status_code, 403)

    def test_every_storefront_page_loads_the_script(self):
        html = Client().get('/').content.decode()
        self.assertIn('storefront/csrf-refresh.js', html)
