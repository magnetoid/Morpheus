"""`orders` query sort-key whitelist (v0.56.0).

A raw caller-supplied `order_by` reached Django's `.order_by()`, where an unknown
field raises FieldError (500) and a relation span leaks/DoSes. The resolver now
falls back to the default for anything off the whitelist.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from plugins.installed.orders.graphql.queries import OrdersQueryExtension


class _Info:
    def __init__(self, request):
        self.context = {'request': request}


def _staff_info():
    req = RequestFactory().post('/graphql/')
    req.user = get_user_model().objects.create_user(
        username='ord-staff', email='ord@ex.test', password='pw', is_staff=True
    )
    return _Info(req)


class OrdersSortWhitelistTests(TestCase):
    def test_malicious_order_by_does_not_raise(self):
        # A relation span that would FieldError / leak — must fall back, not 500.
        result = OrdersQueryExtension().orders(_staff_info(), order_by='customer__password')
        self.assertEqual(result, [])  # no orders exist; the point is it didn't raise

    def test_valid_order_by_is_honoured(self):
        result = OrdersQueryExtension().orders(_staff_info(), order_by='total')
        self.assertEqual(result, [])
