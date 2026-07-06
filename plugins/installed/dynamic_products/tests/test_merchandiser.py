"""AI merchandiser autopilot (Phase 3).

A nightly, propose-only merchandiser files MerchandisingProposal rows into a
human-checkpoint review queue; a staff member approves (applies a low-risk config
action) or dismisses. These tests cover auto-provisioning, proposal generation +
dedup, safe application, and the review page.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.dynamic_products import autopilot
from plugins.installed.dynamic_products.models import (
    DynamicBlock,
    DynamicGridItem,
    MerchandisingProposal,
)

Customer = get_user_model()


def _product(slug, *, featured=False):
    return Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('10.00'), 'USD'),
        status='active',
        is_featured=featured,
    )


class EnsureDefaultBlocksTests(TestCase):
    def test_provisions_idempotently(self):
        self.assertEqual(autopilot.ensure_default_blocks(), 2)  # two default slots
        self.assertEqual(autopilot.ensure_default_blocks(), 0)  # idempotent
        self.assertEqual(DynamicBlock.objects.filter(strategy='autopilot').count(), 2)


class GenerateProposalsTests(TestCase):
    def test_proposes_enable_autopilot_and_dedupes(self):
        self.assertGreaterEqual(autopilot.generate_proposals()['created'], 1)
        self.assertTrue(
            MerchandisingProposal.objects.filter(
                kind='enable_autopilot', status='proposed'
            ).exists()
        )
        # Running again must not duplicate the still-open proposal.
        autopilot.generate_proposals()
        self.assertEqual(
            MerchandisingProposal.objects.filter(signature='enable_autopilot').count(), 1
        )

    def test_features_unfeatured_high_propensity(self):
        p = _product('star')  # active, not featured
        DynamicGridItem.objects.create(product=p, title='Star', purchase_probability=0.95)
        autopilot.generate_proposals()
        prop = MerchandisingProposal.objects.filter(kind='feature_products').first()
        self.assertIsNotNone(prop)
        self.assertIn(str(p.id), prop.payload['product_ids'])


class ApplyProposalTests(TestCase):
    def test_approve_enable_autopilot_provisions_blocks(self):
        prop = MerchandisingProposal.objects.create(
            kind='enable_autopilot',
            title='On',
            signature='enable_autopilot',
            payload={'slots': ['home_above_grid']},
        )
        self.assertTrue(autopilot.apply_proposal(prop))
        prop.refresh_from_db()
        self.assertEqual(prop.status, 'approved')
        self.assertTrue(
            DynamicBlock.objects.filter(slot='home_above_grid', strategy='autopilot').exists()
        )

    def test_approve_feature_sets_is_featured(self):
        p = _product('feat')
        prop = MerchandisingProposal.objects.create(
            kind='feature_products',
            title='Feature',
            signature='feature_products',
            payload={'product_ids': [str(p.id)]},
        )
        self.assertTrue(autopilot.apply_proposal(prop))
        p.refresh_from_db()
        self.assertTrue(p.is_featured)

    def test_insight_is_acknowledged_not_applied(self):
        prop = MerchandisingProposal.objects.create(kind='insight', title='FYI', signature='fyi')
        self.assertFalse(autopilot.apply_proposal(prop))  # nothing applied
        prop.refresh_from_db()
        self.assertEqual(prop.status, 'approved')

    def test_dismiss(self):
        prop = MerchandisingProposal.objects.create(kind='insight', title='x', signature='x')
        autopilot.dismiss_proposal(prop)
        prop.refresh_from_db()
        self.assertEqual(prop.status, 'dismissed')


class ReviewPageTests(TestCase):
    def setUp(self):
        self.staff = Customer.objects.create_user(
            username='s', email='s@x.io', password='pw', is_staff=True
        )

    def test_renders_for_staff(self):
        self.client.force_login(self.staff)
        resp = self.client.get('/dashboard/dynamic-products/proposals/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Autopilot proposals')

    def test_anon_blocked(self):
        resp = self.client.get('/dashboard/dynamic-products/proposals/')
        self.assertIn(resp.status_code, (301, 302, 403))

    def test_approve_via_post(self):
        self.client.force_login(self.staff)
        prop = MerchandisingProposal.objects.create(
            kind='enable_autopilot',
            title='On',
            signature='enable_autopilot',
            payload={'slots': ['home_above_grid']},
        )
        resp = self.client.post(
            f'/dashboard/dynamic-products/proposals/{prop.id}/', {'action': 'approve'}
        )
        self.assertEqual(resp.status_code, 302)
        prop.refresh_from_db()
        self.assertEqual(prop.status, 'approved')


class WiringTests(TestCase):
    def test_merchandiser_task_and_beat_registered(self):
        from django.conf import settings

        from plugins.installed.dynamic_products.tasks import (
            generate_merchandising_proposals as task,
        )

        self.assertEqual(task.name, 'dynamic_products.generate_merchandising_proposals')
        self.assertIn('dynamic_products:merchandiser', settings.CELERY_BEAT_SCHEDULE)
