"""Ops-proposal inbox + activity feed — staged-changes design §3
(docs/superpowers/specs/2026-07-05-staged-changes-routines-design.md).

Permission boundary tests per house rules: anonymous blocked, authed
non-staff blocked, staff allowed — for both the page and the action POST.
"""

# Lazy plugin imports inside helpers are intentional (plugin load-order isolation).
# ruff: noqa: PLC0415
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from djmoney.money import Money

from core.assistant.models import OpsProposal
from core.assistant.staging import stage_proposal


def _product(**kw):
    from plugins.installed.catalog.models import Product

    defaults = {
        'name': 'Inbox widget',
        'slug': 'inbox-widget',
        'sku': 'INB-1',
        'status': 'active',
        'price': Money(Decimal('10.00'), 'USD'),
    }
    defaults.update(kw)
    return Product.objects.create(**defaults)


def _proposal(product=None, **kw):
    product = product or _product()
    defaults = {
        'source': 'routine:catalog-hygiene',
        'kind': 'product.update',
        'title': 'Archive the inbox widget',
        'summary': 'It has been draft for months.',
        'changes': [
            {
                'object': f'catalog.product:{product.pk}',
                'field': 'status',
                'old': 'active',
                'new': 'archived',
            }
        ],
        'target': product,
    }
    defaults.update(kw)
    return stage_proposal(**defaults), product


class OpsInboxPageTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            username='staff', email='staff@example.com', password='x', is_staff=True
        )
        self.customer = user_model.objects.create_user(
            username='cust', email='cust@example.com', password='x'
        )
        self.url = reverse('assistant:proposals')

    def test_anonymous_blocked(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_non_staff_blocked(self):
        self.client.force_login(self.customer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_staff_sees_ops_proposals(self):
        proposal, _product_ = _proposal()
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ops proposals')
        self.assertContains(response, proposal.title)
        self.assertContains(response, 'routine:catalog-hygiene')
        # before → after table cells from `changes`
        self.assertContains(response, 'archived')

    def test_status_filter_chips(self):
        pending, product = _proposal()
        rejected, _ = _proposal(
            product=product, title='Rejected proposal title', kind='product.update'
        )
        OpsProposal.objects.filter(pk=rejected.pk).update(status='rejected')
        self.client.force_login(self.staff)
        # Default chip: proposed only.
        response = self.client.get(self.url)
        self.assertContains(response, pending.title)
        self.assertNotContains(response, 'Rejected proposal title')
        # 'all' shows both.
        response = self.client.get(self.url, {'ops_status': 'all'})
        self.assertContains(response, pending.title)
        self.assertContains(response, 'Rejected proposal title')


class OpsProposalActionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            username='staff2', email='staff2@example.com', password='x', is_staff=True
        )
        self.customer = user_model.objects.create_user(
            username='cust2', email='cust2@example.com', password='x'
        )
        self.proposal, self.product = _proposal()
        self.url = reverse(
            'assistant:ops_proposal_action', kwargs={'proposal_id': self.proposal.pk}
        )

    def _post(self, action):
        return self.client.post(self.url, {'action': action})

    def test_anonymous_blocked(self):
        response = self._post('approve_apply')
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, 'proposed')

    def test_non_staff_blocked(self):
        self.client.force_login(self.customer)
        response = self._post('approve_apply')
        self.assertEqual(response.status_code, 302)
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, 'proposed')
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, 'active')

    def test_approve_apply_happy_path(self):
        self.client.force_login(self.staff)
        response = self.client.post(self.url, {'action': 'approve_apply'}, follow=True)
        self.assertRedirects(response, reverse('assistant:proposals'))
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, 'applied')
        self.assertEqual(self.proposal.approved_by, self.staff)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, 'archived')
        flashes = [str(m) for m in response.context['messages']]
        self.assertTrue(any('1 applied' in m for m in flashes), flashes)

    def test_reject(self):
        self.client.force_login(self.staff)
        response = self._post('reject')
        self.assertEqual(response.status_code, 302)
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, 'rejected')
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, 'active')

    def test_expired_proposal_is_not_applied(self):
        OpsProposal.objects.filter(pk=self.proposal.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        self.client.force_login(self.staff)
        self._post('approve_apply')
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, 'expired')
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, 'active')

    def test_unknown_action_changes_nothing(self):
        self.client.force_login(self.staff)
        response = self._post('bogus')
        self.assertEqual(response.status_code, 302)
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, 'proposed')


class OpsProposalActivityFeedTests(TestCase):
    def _feed(self):
        from core.hooks import MorpheusEvents, hook_registry

        items = hook_registry.filter(MorpheusEvents.ACTIVITY_FEED, value=[], limit=20)
        return [it for it in items if it.get('kind') == 'ops_proposal']

    def test_item_appears_when_proposals_pending(self):
        product = _product()
        older, _ = _proposal(product=product, title='Older proposal')
        # Deterministic ordering — auto_now_add can give identical timestamps.
        OpsProposal.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timedelta(minutes=5)
        )
        newest, _ = _proposal(product=product, title='Newest proposal')
        newest.refresh_from_db()
        items = self._feed()
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item['icon'], 'inbox')
        self.assertEqual(item['label'], '2 staged change(s) awaiting review')
        self.assertEqual(item['hint'], 'Newest proposal')
        self.assertEqual(item['url'], '/dashboard/assistant/proposals/')
        self.assertEqual(item['when'], newest.created_at)

    def test_no_item_when_nothing_pending(self):
        proposal, _ = _proposal()
        OpsProposal.objects.filter(pk=proposal.pk).update(status='rejected')
        self.assertEqual(self._feed(), [])
