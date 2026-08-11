"""Affiliates contributes its transactional emails to the central registry."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import SimpleTestCase, TestCase

from plugins.installed.affiliates.app import AffiliatesPlugin


class AffiliateEmailContributionTests(SimpleTestCase):
    def test_contributes_affiliate_approved_template(self):
        defs = {d.key: d for d in AffiliatesPlugin().contribute_email_templates()}
        self.assertIn('affiliate_approved', defs)
        self.assertEqual(defs['affiliate_approved'].group, 'Affiliates')
        # Default bodies ship with the plugin so the central editor can
        # show/restore them.
        from django.template.loader import get_template

        self.assertTrue(get_template('emails/affiliate_approved.txt'))
        self.assertTrue(get_template('emails/affiliate_approved.html'))


class AffiliateApprovedSendTests(TestCase):
    def _affiliate(self, status='pending'):
        from plugins.installed.affiliates.models import Affiliate, AffiliateProgram

        u = get_user_model().objects.create_user(
            username='aff', email='aff@example.test', password='pw'
        )
        prog, _ = AffiliateProgram.objects.get_or_create(
            slug='default', defaults={'name': 'Default'}
        )
        return Affiliate.objects.create(program=prog, user=u, handle='aff', status=status)

    def test_approving_a_pending_affiliate_sends_one_email(self):
        from django.test import override_settings

        from plugins.installed.affiliates.dashboard import _affiliate_apply_status

        aff = self._affiliate(status='pending')
        with override_settings(DEFAULT_FROM_EMAIL='store@example.test'):
            self.assertTrue(_affiliate_apply_status(aff, 'approve'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['aff@example.test'])

    def test_re_approving_already_approved_sends_nothing(self):
        from django.test import override_settings

        from plugins.installed.affiliates.dashboard import _affiliate_apply_status

        aff = self._affiliate(status='approved')
        with override_settings(DEFAULT_FROM_EMAIL='store@example.test'):
            _affiliate_apply_status(aff, 'reactivate')
        self.assertEqual(len(mail.outbox), 0)
