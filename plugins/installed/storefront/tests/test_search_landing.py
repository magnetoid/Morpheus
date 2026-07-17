"""The /search/ landing renders the mood-search page instead of bouncing away.

A query-less /search/ must render the semantic "describe what you're in the
mood for" landing (200). It used to 302 to /products/, which made the mood
panel — living in the {% if not query %} empty state — unreachable through
normal navigation. A *keyword* search (?q=…) still bounces to the rich PLP.
"""

from __future__ import annotations

from django.test import Client, TestCase


class SearchLandingTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_empty_search_renders_mood_landing(self):
        resp = self.client.get('/search/')
        self.assertEqual(resp.status_code, 200)
        # the mood-search textarea is the reachable proof of the empty state
        self.assertContains(resp, 'mood-q')

    def test_keyword_search_redirects_to_plp(self):
        resp = self.client.get('/search/', {'q': 'dickens'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/products/?q=dickens')
