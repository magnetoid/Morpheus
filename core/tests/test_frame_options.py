"""The store may frame itself; nobody else may frame the store or the dashboard.

`X_FRAME_OPTIONS = 'DENY'` also refused SAME-origin framing, and browsers
enforce it: the dashboard's Theme builder previews a page in
`<iframe src="/p/<slug>/?preview=1">`, which rendered blank. The storefront's
report-only CSP said `frame-ancestors 'none'` for the same reason and logged
the store framing itself as a violation. SAMEORIGIN keeps every other origin
out; the dashboard keeps its own enforcing `frame-ancestors 'none'`, which
browsers apply over X-Frame-Options.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase


class FrameOptionsTests(TestCase):
    def test_storefront_pages_may_be_framed_by_the_store_itself(self):
        resp = self.client.get('/')
        self.assertEqual(resp['X-Frame-Options'], 'SAMEORIGIN')
        self.assertIn("frame-ancestors 'self'", resp['Content-Security-Policy-Report-Only'])

    def test_the_dashboard_still_refuses_every_frame(self):
        staff = get_user_model().objects.create_user(
            username='frame-staff', email='frame@x.test', password='pw', is_staff=True
        )
        self.client.force_login(staff)
        resp = self.client.get('/dashboard/')
        self.assertIn("frame-ancestors 'none'", resp['Content-Security-Policy'])
