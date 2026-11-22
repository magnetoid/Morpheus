"""The pageview script runs on a payment page.

A payment page (the basket, the checkout steps, saved cards) enforces a policy
that runs a script only when its tag carries the response's nonce
(`core/security_headers.py`). The middleware that adds the pageview script read
`request.csp_nonce`, which Django never sets (it keeps the nonce in
`request._csp_nonce`, read through `django.middleware.csp.get_nonce`), so the
script went out without one, the browser refused it, and no basket or checkout
page was ever counted.
"""

from __future__ import annotations

import re

from django.core.cache import cache
from django.test import Client, TestCase

_BROWSER = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Version/17.5 Safari/605.1.15'
)
_HIT = re.compile(rb'<script[^>]*\bdata-morph-hit\b[^>]*>')


class PaymentPageBeaconTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_the_basket_page_script_carries_the_policys_nonce(self):
        response = Client(HTTP_USER_AGENT=_BROWSER).get('/cart/')
        self.assertEqual(response.status_code, 200)
        policy = response.get('Content-Security-Policy', '')
        nonce = re.search(r"'nonce-([^']+)'", policy)
        self.assertIsNotNone(nonce, policy)
        tag = _HIT.search(response.content)
        self.assertIsNotNone(tag, 'the basket page carries no pageview script')
        self.assertIn(f'nonce="{nonce.group(1)}"'.encode(), tag.group(0))

    def test_a_page_under_the_report_only_policy_keeps_its_script(self):
        response = Client(HTTP_USER_AGENT=_BROWSER).get('/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.has_header('Content-Security-Policy'))
        self.assertIsNotNone(_HIT.search(response.content))
