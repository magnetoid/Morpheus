"""Server-side assistant-mode entitlement (core audit S5/H1).

A client supplies a `mode`, but it must never let the acting user select a mode
above their ceiling — in particular `dev` (diagnostics: filesystem, logs, plugin
lifecycle) is engineer-only, and an unknown slug must not escalate to the
`general` wildcard.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.assistant.modes import allowed_modes_for, resolve_mode

User = get_user_model()


class ModeEntitlementTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='eng', email='eng@x.com', password='x', is_staff=True, is_superuser=True
        )
        self.staff = User.objects.create_user(
            username='support', email='s@x.com', password='x', is_staff=True
        )

    def test_staff_cannot_select_dev(self):
        # The escalation: a non-engineer requesting diagnostics access.
        self.assertNotEqual(resolve_mode('dev', self.staff).slug, 'dev')
        self.assertNotIn('dev', allowed_modes_for(self.staff))

    def test_superuser_can_select_dev(self):
        self.assertEqual(resolve_mode('dev', self.superuser).slug, 'dev')

    def test_unknown_mode_does_not_escalate_to_dev(self):
        # Garbage slug → the user's default, never the elevated dev mode.
        self.assertNotEqual(resolve_mode('garbage-xyz', self.staff).slug, 'dev')
        self.assertNotEqual(resolve_mode('', self.staff).slug, 'dev')

    def test_entitled_mode_is_honoured(self):
        self.assertEqual(resolve_mode('support', self.staff).slug, 'support')
        self.assertEqual(resolve_mode('ops', self.staff).slug, 'ops')

    def test_no_user_gets_narrow_floor_not_wildcard(self):
        mode = resolve_mode('general', None)
        self.assertNotIn('*', mode.scopes)
        self.assertEqual(allowed_modes_for(None), set())
