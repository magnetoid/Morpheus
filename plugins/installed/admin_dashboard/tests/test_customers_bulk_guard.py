"""Bulk customer delete must respect the staff-account guard.

The single-record delete refuses staff/superuser accounts; a bulk selection
that sweeps one in must not bypass that (it used to: ``qs.delete()`` with no
filter would hard-delete an admin along with the customers).
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

User = get_user_model()


class CustomersBulkDeleteGuardTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='admin', email='admin@example.com', password='x', is_staff=True
        )
        self.customer = User.objects.create_user(
            username='shopper', email='shopper@example.com', password='x'
        )
        self.client = Client()
        self.client.force_login(self.staff)

    def _bulk_delete(self, *users):
        return self.client.post(
            '/dashboard/customers/bulk/',
            {'action': 'delete', 'ids': [str(u.pk) for u in users]},
        )

    def test_bulk_delete_skips_staff_accounts(self):
        superuser = User.objects.create_superuser(
            username='root', email='root@example.com', password='x'
        )
        self._bulk_delete(self.customer, self.staff, superuser)
        # the plain customer is gone…
        self.assertFalse(User.objects.filter(pk=self.customer.pk).exists())
        # …but staff + superuser survive, exactly like the single-record guard
        self.assertTrue(User.objects.filter(pk=self.staff.pk).exists())
        self.assertTrue(User.objects.filter(pk=superuser.pk).exists())

    def test_bulk_delete_plain_customers_still_works(self):
        other = User.objects.create_user(username='b', email='b@example.com', password='x')
        self._bulk_delete(self.customer, other)
        self.assertEqual(
            User.objects.filter(pk__in=[self.customer.pk, other.pk]).count(),
            0,
        )
