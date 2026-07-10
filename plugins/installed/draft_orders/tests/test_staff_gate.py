"""Dashboard draft-order views are staff-only (were @login_required — any
signed-in customer could list, mutate, and CONVERT drafts into orders)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase


class DraftOrderStaffGateTests(TestCase):
    def _client(self, *, staff):
        user = get_user_model().objects.create_user(
            username=f'u-{staff}', email=f'{staff}@example.com', password='x', is_staff=staff
        )
        c = Client()
        c.force_login(user)
        return c

    def test_customer_cannot_reach_draft_orders(self):
        resp = self._client(staff=False).get('/dashboard/draft-orders/')
        self.assertIn(resp.status_code, (302, 403))

    def test_staff_can_reach_draft_orders(self):
        resp = self._client(staff=True).get('/dashboard/draft-orders/')
        self.assertEqual(resp.status_code, 200)
