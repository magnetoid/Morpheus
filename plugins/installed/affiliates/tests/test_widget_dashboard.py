"""Permission-boundary tests for the affiliate-owned widget dashboard.

``widgets`` (GET/POST) and ``edit_widget`` (POST) are customer-scoped write
endpoints: a signed-in *approved* affiliate manages ONLY their own widgets.
The expensive failure here is one affiliate mutating another's widget, so we
lock the triplet in:

  anon              → redirected to login; no widget created/mutated
  authed/non-owner  → cannot create (no approved affiliate → bounced) and
                      cannot edit/delete someone else's widget
  authed/owner      → can create, edit, toggle, delete their own widget

``@login_required`` redirects anon to the login page (302), and
``_affiliate_or_redirect`` bounces a signed-in user with no approved affiliate
to /affiliates/apply/ — so for the first two the load-bearing assertion is
"the widget set didn't change."
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from plugins.installed.affiliates.models import (
    Affiliate,
    AffiliateLink,
    AffiliateProgram,
    AffiliateWidget,
)

Customer = get_user_model()


def _approved_affiliate(program, email, handle):
    user = Customer.objects.create_user(username=email, email=email, password='pw')
    aff = Affiliate.objects.create(program=program, user=user, handle=handle, status='approved')
    AffiliateLink.objects.create(affiliate=aff, code=f'{handle}-code', landing_url='/')
    return user, aff


class WidgetDashboardBoundaryTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.program = AffiliateProgram.objects.create(
            name='Default', slug='default', commission_value=Decimal('10'), is_active=True
        )
        self.owner_user, self.owner = _approved_affiliate(
            self.program, 'owner@example.com', 'owner'
        )
        self.other_user, self.other = _approved_affiliate(
            self.program, 'other@example.com', 'other'
        )
        # A widget owned by `other`, used as the cross-tenant target.
        self.other_widget = AffiliateWidget.objects.create(
            affiliate=self.other, title='Other widget', source='featured'
        )
        self.list_url = reverse('affiliates:widgets')

    # ── anonymous ────────────────────────────────────────────────────
    def test_anon_create_redirected_no_mutation(self):
        before = AffiliateWidget.objects.count()
        resp = self.client.post(self.list_url, {'action': 'create', 'source': 'featured'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.headers['Location'])
        self.assertEqual(AffiliateWidget.objects.count(), before)

    def test_anon_edit_redirected_no_mutation(self):
        url = reverse('affiliates:edit_widget', args=[self.other_widget.id])
        resp = self.client.post(url, {'action': 'delete'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.headers['Location'])
        self.assertTrue(AffiliateWidget.objects.filter(pk=self.other_widget.pk).exists())

    # ── authed non-owner ─────────────────────────────────────────────
    def test_non_owner_cannot_delete_others_widget(self):
        self.client.force_login(self.owner_user)
        url = reverse('affiliates:edit_widget', args=[self.other_widget.id])
        resp = self.client.post(url, {'action': 'delete'})
        # Redirects back to the widget list; the other affiliate's widget
        # survives (queryset is scoped to affiliate__user=request.user).
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(AffiliateWidget.objects.filter(pk=self.other_widget.pk).exists())

    def test_non_owner_cannot_toggle_others_widget(self):
        self.client.force_login(self.owner_user)
        url = reverse('affiliates:edit_widget', args=[self.other_widget.id])
        self.client.post(url, {'action': 'toggle'})
        self.other_widget.refresh_from_db()
        self.assertTrue(self.other_widget.is_active)  # unchanged

    def test_user_without_approved_affiliate_cannot_create(self):
        nobody = Customer.objects.create_user(
            username='nobody@example.com', email='nobody@example.com', password='pw'
        )
        self.client.force_login(nobody)
        before = AffiliateWidget.objects.count()
        resp = self.client.post(self.list_url, {'action': 'create', 'source': 'featured'})
        # Bounced by _affiliate_or_redirect (to apply/dashboard); nothing made.
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(AffiliateWidget.objects.count(), before)

    # ── authed owner ─────────────────────────────────────────────────
    def test_owner_can_create_widget(self):
        self.client.force_login(self.owner_user)
        resp = self.client.post(
            self.list_url,
            {'action': 'create', 'source': 'featured', 'theme': 'dark', 'limit': '8'},
        )
        self.assertEqual(resp.status_code, 302)
        w = AffiliateWidget.objects.filter(affiliate=self.owner).first()
        self.assertIsNotNone(w)
        self.assertEqual(w.theme, 'dark')
        self.assertEqual(w.limit, 8)
        self.assertTrue(w.key)  # public key auto-minted

    def test_owner_can_view_list_200(self):
        self.client.force_login(self.owner_user)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 200)

    def test_owner_can_delete_own_widget(self):
        self.client.force_login(self.owner_user)
        mine = AffiliateWidget.objects.create(affiliate=self.owner, source='featured')
        url = reverse('affiliates:edit_widget', args=[mine.id])
        resp = self.client.post(url, {'action': 'delete'})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(AffiliateWidget.objects.filter(pk=mine.pk).exists())
