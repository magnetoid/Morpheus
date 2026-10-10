"""A turn token also names the provider and model the turn runs on, so the MCP
edge can write them on every decision row (the AI-Act export counted zero
decisions by model on every store: nothing at the edge knew the model)."""

from __future__ import annotations

from django.test import SimpleTestCase

from core.assistant.turn_identity import mint, verify


class _User:
    pk = 7


class TurnTokenClaimTests(SimpleTestCase):
    def test_provider_and_model_ride_along(self):
        token = mint(
            user=_User(),
            conversation_key='user:7',
            mode_slug='',
            ttl_s=60,
            provider='deepseek',
            model='deepseek-chat',
        )
        identity = verify(token)
        self.assertEqual((identity.provider, identity.model), ('deepseek', 'deepseek-chat'))

    def test_a_token_without_them_still_verifies(self):
        identity = verify(mint(user=_User(), conversation_key='user:7', mode_slug='', ttl_s=60))
        self.assertIsNotNone(identity)
        self.assertEqual((identity.provider, identity.model), ('', ''))
