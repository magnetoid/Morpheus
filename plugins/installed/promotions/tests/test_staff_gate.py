"""The promotions dashboard is staff-only (was @login_required — any
signed-in customer could read the full promotion ruleset)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase


class PromotionsStaffGateTests(TestCase):
    def _client(self, *, staff):
        user = get_user_model().objects.create_user(
            username=f'p-{staff}', email=f'p{staff}@example.com', password='x', is_staff=staff
        )
        c = Client()
        c.force_login(user)
        return c

    def test_customer_cannot_reach_promotions_dashboard(self):
        resp = self._client(staff=False).get('/dashboard/promotions/')
        self.assertIn(resp.status_code, (302, 403))

    def test_staff_can_reach_promotions_dashboard(self):
        resp = self._client(staff=True).get('/dashboard/promotions/')
        self.assertEqual(resp.status_code, 200)
