"""Cloudflare leaves dashboard pages alone, so staff see real email addresses.

Its Email Address Obfuscation turns every address in an HTML page into
"[email protected]" and decodes it with a script that runs on a full page load
only; the dashboard navigates with hx-boost, so pages reached by a link stayed
encoded. Cloudflare skips any response carrying ``Cache-Control: no-transform``.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase


class DashboardNoTransformTests(TestCase):
    def test_every_dashboard_response_says_no_transform(self):
        resp = Client().get('/dashboard/')  # the sign-in redirect too
        self.assertIn('no-transform', resp.headers.get('Cache-Control', ''))

    def test_a_signed_in_dashboard_page_says_no_transform(self):
        staff = get_user_model().objects.create_user(
            username='nt-staff', email='nt@shop.test', password='pw', is_staff=True
        )
        c = Client()
        c.force_login(staff)
        resp = c.get('/dashboard/crm/inbox/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('no-transform', resp.headers.get('Cache-Control', ''))

    def test_the_storefront_is_not_affected(self):
        resp = Client().get('/robots.txt')
        self.assertNotIn('no-transform', resp.headers.get('Cache-Control', ''))
