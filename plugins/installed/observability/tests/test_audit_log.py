"""Audit-log dashboard — RBAC + category filtering."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from core.audit.models import AuditEvent

URL = '/dashboard/observability/audit/'


class AuditLogViewTests(TestCase):
    def setUp(self):
        AuditEvent.objects.create(event_type='agents.decision', target='run/1', actor_label='linda')
        AuditEvent.objects.create(
            event_type='selfdev.apply', target='proposal/2', severity='warning'
        )
        AuditEvent.objects.create(event_type='rbac.role_granted', target='user/3')
        AuditEvent.objects.create(event_type='order.placed', target='order/4')
        self.c = Client()
        self.c.force_login(
            get_user_model().objects.create_user(
                username='s', email='s@x.test', password='pw', is_staff=True
            )
        )

    def test_requires_staff(self):
        self.assertEqual(Client().get(URL).status_code, 302)

    def test_all_shows_everything(self):
        r = self.c.get(URL)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'agents.decision')
        self.assertContains(r, 'order.placed')

    def test_ai_category_filters(self):
        r = self.c.get(URL + '?category=ai')
        self.assertContains(r, 'agents.decision')
        self.assertContains(r, 'selfdev.apply')
        self.assertNotContains(r, 'order.placed')
        self.assertNotContains(r, 'rbac.role_granted')

    def test_security_category_filters(self):
        r = self.c.get(URL + '?category=security')
        self.assertContains(r, 'rbac.role_granted')
        self.assertNotContains(r, 'agents.decision')

    def test_search_and_severity(self):
        self.assertContains(self.c.get(URL + '?q=order/4'), 'order.placed')
        r = self.c.get(URL + '?severity=warning')
        self.assertContains(r, 'selfdev.apply')
        self.assertNotContains(r, 'order.placed')

    def test_plugin_contributes_audit_page(self):
        from plugins.installed.observability.app import ObservabilityPlugin

        slugs = {p.slug for p in ObservabilityPlugin().contribute_dashboard_pages()}
        self.assertIn('audit', slugs)
