"""The NPS thank-you page must be reachable after submitting a score.

`nps/<str:token>/` was registered BEFORE `nps/thanks/`, and `str` matches
"thanks" — so Django resolved the post-submit redirect back into
`nps_form(token='thanks')`, which fails signature verification and renders
"link expired" with HTTP 410. Every customer who rated their order saw that
instead of a thank-you. Route order is the whole fix, so route order is what
these tests pin.
"""

from __future__ import annotations

from django.core.signing import TimestampSigner
from django.test import TestCase
from django.urls import resolve, reverse


class NpsRouteOrderTests(TestCase):
    def test_thanks_url_resolves_to_the_thanks_view(self):
        match = resolve('/post-purchase/nps/thanks/')
        self.assertEqual(match.func.__name__, 'nps_thanks')

    def test_thanks_page_renders(self):
        resp = self.client.get(reverse('post_purchase:nps_thanks'))
        self.assertEqual(resp.status_code, 200)

    def test_a_real_token_still_reaches_the_form(self):
        # The reorder must not shadow the token route it precedes.
        token = TimestampSigner(salt='post_purchase.nps').sign('nonexistent-pk')
        match = resolve(f'/post-purchase/nps/{token}/')
        self.assertEqual(match.func.__name__, 'nps_form')
