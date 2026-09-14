"""Signed per-turn identity for Linda's Janus engine."""

from __future__ import annotations

import secrets
import time
import types
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from core.assistant import turn_identity as ti


def _user(pk=7):
    return types.SimpleNamespace(pk=pk)


class TurnTokenTests(SimpleTestCase):
    def test_round_trip(self):
        token = ti.mint(user=_user(), conversation_key='user:7', mode_slug='sales', ttl_s=60)
        identity = ti.verify(token)
        self.assertEqual(
            (identity.user_id, identity.conversation_key, identity.mode), ('7', 'user:7', 'sales')
        )

    def test_prefix_distinguishes_it_from_api_keys(self):
        token = ti.mint(user=_user(), conversation_key='c', mode_slug='general', ttl_s=60)
        self.assertTrue(ti.is_turn_token(token))
        self.assertFalse(ti.is_turn_token('tok-plain'))
        self.assertIsNone(ti.verify('tok-plain'))

    def test_tampering_is_detected(self):
        token = ti.mint(user=_user(), conversation_key='c', mode_slug='general', ttl_s=60)
        self.assertIsNone(ti.verify(token[:-3] + 'abc'))

    def test_expiry(self):
        token = ti.mint(user=_user(), conversation_key='c', mode_slug='general', ttl_s=5)
        with mock.patch.object(ti.time, 'time', return_value=time.time() + 60):
            self.assertIsNone(ti.verify(token))

    def test_tokens_are_unique_per_turn(self):
        a = ti.mint(user=_user(), conversation_key='c', mode_slug='general', ttl_s=60)
        b = ti.mint(user=_user(), conversation_key='c', mode_slug='general', ttl_s=60)
        self.assertNotEqual(a, b)

    def test_another_secret_key_cannot_forge_one(self):
        # Another deployment's key, generated so no literal secret sits in the tree.
        with override_settings(SECRET_KEY=secrets.token_urlsafe(50)):
            forged = ti.mint(user=_user(), conversation_key='c', mode_slug='dev', ttl_s=60)
        self.assertIsNone(ti.verify(forged))


class ResolveUserTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='staffer', email='s@example.com', password='x', is_staff=True
        )

    def _identity(self):
        token = ti.mint(user=self.user, conversation_key='c', mode_slug='general', ttl_s=60)
        return ti.verify(token)

    def test_active_staff_resolves(self):
        self.assertEqual(ti.resolve_user(self._identity()), self.user)

    def test_non_staff_does_not_resolve(self):
        identity = self._identity()
        self.user.is_staff = False
        self.user.save(update_fields=['is_staff'])
        self.assertIsNone(ti.resolve_user(identity))

    def test_deactivated_user_does_not_resolve(self):
        identity = self._identity()
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertIsNone(ti.resolve_user(identity))


class MintForTurnTests(SimpleTestCase):
    """What Assistant hands the engine."""

    def test_no_staff_user_means_no_token(self):
        from core.assistant.runtime import Assistant

        a = Assistant()
        self.assertEqual(a._mint_turn_token({}, 'c'), '')
        self.assertEqual(
            a._mint_turn_token({'user': types.SimpleNamespace(pk=1, is_staff=False)}, 'c'), ''
        )

    def test_staff_user_gets_a_token_for_their_conversation_and_resolved_mode(self):
        from core.assistant.runtime import Assistant

        staff = types.SimpleNamespace(pk=3, is_staff=True, is_superuser=False)
        token = Assistant()._mint_turn_token({'user': staff, 'mode': 'dev'}, 'user:3')
        identity = ti.verify(token)
        self.assertEqual(identity.conversation_key, 'user:3')
        # `dev` is superuser-only, so a staff member's request resolves to general.
        self.assertEqual(identity.mode, 'general')
