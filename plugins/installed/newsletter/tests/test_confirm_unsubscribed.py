"""Regression — confirm() refuses to resurrect an unsubscribed subscriber.

Guards Fix 10: ``confirm(token)`` used to flip any non-'confirmed' row to
'confirmed', so an ``unsubscribed`` (terminal) row got silently re-added to the
mailable audience via its still-valid original confirm link. The fix returns
None before promoting when ``status == 'unsubscribed'``; re-opting-in must go
through ``subscribe()`` (which resets to 'pending' + re-sends consent).
"""

from __future__ import annotations

from django.test import TestCase, override_settings

from plugins.installed.newsletter.services import confirm, subscribe, unsubscribe


@override_settings(DEFAULT_FROM_EMAIL='store@example.test')
class ConfirmUnsubscribedTests(TestCase):
    def test_stale_confirm_link_cannot_resurrect_unsubscribed(self):
        sub, _ = subscribe('gone@example.test')
        confirm(sub.confirm_token)
        unsubscribe(sub.confirm_token)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'unsubscribed')
        prev_confirmed_at = sub.confirmed_at

        # Clicking the ORIGINAL confirm link again must NOT re-add them.
        result = confirm(sub.confirm_token)

        self.assertIsNone(result)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'unsubscribed')  # NOT resurrected
        self.assertEqual(sub.confirmed_at, prev_confirmed_at)  # not bumped

    def test_pending_still_confirms(self):
        # Sanity: the normal path is untouched.
        sub, _ = subscribe('fresh@example.test')
        self.assertEqual(sub.status, 'pending')

        result = confirm(sub.confirm_token)

        self.assertIsNotNone(result)
        self.assertEqual(result.status, 'confirmed')
        self.assertIsNotNone(result.confirmed_at)

    def test_re_optin_after_unsubscribe_confirms(self):
        # The guard only blocks the stale-link case, not a fresh re-subscribe:
        # subscribe() resets the unsubscribed row to 'pending', then confirm()
        # promotes it to 'confirmed'.
        sub, _ = subscribe('again@example.test')
        confirm(sub.confirm_token)
        unsubscribe(sub.confirm_token)

        resub, _ = subscribe('again@example.test')
        resub.refresh_from_db()
        self.assertEqual(resub.status, 'pending')  # reset by subscribe()

        result = confirm(resub.confirm_token)

        self.assertIsNotNone(result)
        self.assertEqual(result.status, 'confirmed')
