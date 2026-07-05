"""OpsProposal + stage_proposal tests — staged-changes design §1–2
(docs/superpowers/specs/2026-07-05-staged-changes-routines-design.md).
"""

# Lazy plugin imports inside helpers are intentional (plugin load-order isolation).
# ruff: noqa: PLC0415
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from core.assistant.models import OpsProposal
from core.assistant.staging import stage_proposal
from core.safety import SafetyViolation


def _product(**kw):
    from plugins.installed.catalog.models import Product

    defaults = {
        'name': 'Old name',
        'slug': 'ops-prop-product',
        'sku': 'OPS-1',
        'status': 'active',
        'price': Money(Decimal('10.00'), 'USD'),
    }
    defaults.update(kw)
    return Product.objects.create(**defaults)


def _change(product, *, field='name', old='Old name', new='New name'):
    return {'object': f'catalog.product:{product.pk}', 'field': field, 'old': old, 'new': new}


def _stage(**kw):
    defaults = {
        'source': 'routine:catalog-hygiene',
        'kind': 'product.update',
        'title': 'Rename a product',
        'summary': 'because the test says so',
        'changes': [],
    }
    defaults.update(kw)
    return stage_proposal(**defaults)


class StageProposalTests(TestCase):
    def test_stage_creates_proposed_row(self):
        proposal = _stage(
            changes=[{'object': 'catalog.product:x', 'field': 'name', 'old': 'a', 'new': 'b'}]
        )
        self.assertEqual(proposal.status, 'proposed')
        self.assertEqual(proposal.source, 'routine:catalog-hygiene')
        self.assertEqual(proposal.kind, 'product.update')
        self.assertEqual(len(proposal.changes), 1)
        self.assertIsNotNone(proposal.expires_at)
        # default TTL is 7 days
        delta = proposal.expires_at - timezone.now()
        self.assertGreater(delta, timedelta(days=6))
        self.assertLessEqual(delta, timedelta(days=7))
        self.assertEqual(OpsProposal.objects.count(), 1)

    def test_stage_clamps_field_lengths(self):
        proposal = _stage(title='t' * 500, source='s' * 200, kind='k' * 100)
        self.assertEqual(len(proposal.title), 200)
        self.assertEqual(len(proposal.source), 80)
        self.assertEqual(len(proposal.kind), 40)

    def test_blocked_class_raises_safety_violation(self):
        with self.assertRaises(SafetyViolation):
            _stage(kind='pricing_change')
        self.assertEqual(OpsProposal.objects.count(), 0)

    def test_stage_records_generic_fk_target(self):
        product = _product()
        proposal = _stage(target=product)
        proposal.refresh_from_db()
        self.assertEqual(proposal.target, product)


class ApproveTests(TestCase):
    def _proposal(self, **kw):
        return _stage(**kw)

    def test_non_staff_fails_closed(self):
        user_model = get_user_model()
        customer = user_model.objects.create_user(username='cust', password='x')
        proposal = self._proposal()
        with self.assertRaises(PermissionError):
            proposal.approve(customer)
        with self.assertRaises(PermissionError):
            proposal.approve(None)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'proposed')

    def test_staff_approve_flips_status(self):
        user_model = get_user_model()
        staff = user_model.objects.create_user(username='staff', password='x', is_staff=True)
        proposal = self._proposal()
        self.assertTrue(proposal.approve(staff))
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'approved')
        self.assertEqual(proposal.approved_by, staff)
        self.assertIsNotNone(proposal.approved_at)

    def test_approve_expired_flips_to_expired(self):
        user_model = get_user_model()
        staff = user_model.objects.create_user(username='staff2', password='x', is_staff=True)
        proposal = self._proposal()
        proposal.expires_at = timezone.now() - timedelta(minutes=1)
        proposal.save(update_fields=['expires_at'])
        self.assertFalse(proposal.approve(staff))
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'expired')
        self.assertIsNone(proposal.approved_by)

    def test_approve_refuses_non_proposed_status(self):
        user_model = get_user_model()
        staff = user_model.objects.create_user(username='staff3', password='x', is_staff=True)
        proposal = self._proposal()
        proposal.status = 'rejected'
        proposal.save(update_fields=['status'])
        with self.assertRaises(ValueError):
            proposal.approve(staff)


class ApplyTests(TestCase):
    def test_apply_happy_path_mutates_audits_and_flips_status(self):
        from core.audit.models import AuditEvent

        product = _product()
        proposal = _stage(changes=[_change(product)])
        result = proposal.apply()
        self.assertEqual(result['applied'], 1)
        self.assertEqual(result['skipped'], [])
        self.assertEqual(result['errors'], [])
        product.refresh_from_db()
        self.assertEqual(product.name, 'New name')
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'applied')
        self.assertIsNotNone(proposal.applied_at)
        self.assertEqual(proposal.apply_error, '')
        events = AuditEvent.objects.filter(event_type='assistant.ops_proposal.change_applied')
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first().metadata.get('proposal'), str(proposal.pk))

    def test_apply_skips_drifted_change_applies_others(self):
        good = _product(slug='ops-good', sku='OPS-G')
        drifted = _product(slug='ops-drift', sku='OPS-D', name='Live value moved on')
        proposal = _stage(
            changes=[
                _change(good),
                _change(drifted, old='Stale snapshot'),  # live != old → drift
            ]
        )
        result = proposal.apply()
        self.assertEqual(result['applied'], 1)
        self.assertEqual(len(result['skipped']), 1)
        self.assertEqual(result['skipped'][0]['reason'], 'drifted')
        self.assertEqual(result['errors'], [])
        good.refresh_from_db()
        drifted.refresh_from_db()
        self.assertEqual(good.name, 'New name')
        self.assertEqual(drifted.name, 'Live value moved on')  # untouched
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'applied')  # partial success is applied

    def test_apply_resolve_failure_reports_error_and_fails_when_nothing_applied(self):
        proposal = _stage(
            changes=[{'object': 'nonsense.model:999', 'field': 'name', 'old': 'a', 'new': 'b'}]
        )
        result = proposal.apply()
        self.assertEqual(result['applied'], 0)
        self.assertEqual(len(result['errors']), 1)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'failed')
        self.assertNotEqual(proposal.apply_error, '')

    def test_apply_partial_success_is_applied_with_errors_reported(self):
        product = _product(slug='ops-partial', sku='OPS-P')
        proposal = _stage(
            changes=[
                _change(product),
                {'object': 'nonsense.model:999', 'field': 'name', 'old': 'a', 'new': 'b'},
            ]
        )
        result = proposal.apply()
        self.assertEqual(result['applied'], 1)
        self.assertEqual(len(result['errors']), 1)
        product.refresh_from_db()
        self.assertEqual(product.name, 'New name')
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'applied')

    def test_apply_never_raises_on_terminal_status(self):
        proposal = _stage()
        proposal.status = 'rejected'
        proposal.save(update_fields=['status'])
        result = proposal.apply()
        self.assertEqual(result['applied'], 0)
        self.assertEqual(len(result['errors']), 1)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'rejected')  # terminal status untouched
