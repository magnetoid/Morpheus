"""Custom-audience uploads: never staff, only customers who said yes, and only
with the merchant's approval.

`meta.sync_audience` uploaded every user with an email — staff included — under
scope `analytics.read` with no approval (wave 0 item 3).
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.consent.models import ConsentLog
from plugins.installed.meta_commerce.services.audiences import _segment_emails
from plugins.installed.orders.models import Order

User = get_user_model()


def _set_gdpr(on: bool) -> None:
    from core.models import StoreSettings

    row = StoreSettings.objects.first() or StoreSettings()
    row.gdpr_enabled = on
    row.save()
    cache.delete('morph:gdpr_enabled')


class AllCustomersTests(TestCase):
    def setUp(self):
        self.yes = User.objects.create_user(username='y', email='yes@x.test', password='x')
        self.no = User.objects.create_user(username='n', email='no@x.test', password='x')
        self.staff = User.objects.create_user(
            username='s', email='staff@x.test', password='x', is_staff=True
        )
        ConsentLog.objects.create(customer=self.yes, session_key='a', marketing=True)
        ConsentLog.objects.create(customer=self.staff, session_key='b', marketing=True)

    def test_a_managed_store_uploads_only_customers_who_said_yes(self):
        _set_gdpr(True)
        self.assertEqual(_segment_emails('all_customers'), ['yes@x.test'])

    def test_staff_are_never_uploaded(self):
        _set_gdpr(False)
        emails = _segment_emails('all_customers')
        self.assertIn('no@x.test', emails)
        self.assertNotIn('staff@x.test', emails)


class PurchasersTests(TestCase):
    def _order(self, email, consent):
        o = Order.objects.create(
            email=email,
            subtotal=Money(Decimal('5'), 'USD'),
            total=Money(Decimal('5'), 'USD'),
            metadata={'consent': consent} if consent else {},
        )
        Order.objects.filter(pk=o.pk).update(status='confirmed')
        return o

    def test_a_managed_store_uploads_only_stamped_yes_purchasers(self):
        _set_gdpr(True)
        self._order('buyer-yes@x.test', {'managed': True, 'marketing': True})
        self._order('buyer-no@x.test', {'managed': True, 'marketing': False})
        self._order('buyer-old@x.test', None)
        self.assertEqual(_segment_emails('purchasers'), ['buyer-yes@x.test'])


class ToolGateTests(TestCase):
    def test_the_tool_needs_approval_and_a_customer_write_scope(self):
        from core.agents.registry import agent_registry

        tool = agent_registry.get_tool('meta.sync_audience')
        self.assertTrue(tool.requires_approval)
        self.assertEqual(tool.scopes, ['crm.write'])
