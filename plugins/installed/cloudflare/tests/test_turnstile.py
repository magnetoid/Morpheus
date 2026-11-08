"""Cloudflare Turnstile — the verify helper (the forms: test_turnstile_forms.py)."""

# ruff: noqa: PLC0415
from __future__ import annotations

from unittest.mock import patch

from django.test import RequestFactory, TestCase

_CFG = 'plugins.installed.cloudflare.services._turnstile_config'


class TurnstileTests(TestCase):
    def test_disabled_is_not_enforced(self):
        from plugins.installed.cloudflare.services import turnstile_site_key, verify_turnstile

        req = RequestFactory().post('/', {})
        with patch(_CFG, return_value={}):
            self.assertTrue(verify_turnstile(req))  # off → don't block
            self.assertEqual(turnstile_site_key(), '')

    def test_enabled_missing_token_fails_closed(self):
        from plugins.installed.cloudflare.services import verify_turnstile

        req = RequestFactory().post('/', {})
        with patch(_CFG, return_value={'turnstile_enabled': True, 'turnstile_secret_key': 's'}):
            self.assertFalse(verify_turnstile(req))

    def test_enabled_valid_token_succeeds(self):
        from plugins.installed.cloudflare.services import verify_turnstile

        req = RequestFactory().post('/', {'cf-turnstile-response': 'tok'})
        cfg = {'turnstile_enabled': True, 'turnstile_secret_key': 's'}
        with (
            patch(_CFG, return_value=cfg),
            patch('requests.post') as mp,
        ):
            mp.return_value.json.return_value = {'success': True}
            self.assertTrue(verify_turnstile(req))

    def test_site_key_when_enabled(self):
        from plugins.installed.cloudflare.services import turnstile_site_key

        with patch(_CFG, return_value={'turnstile_enabled': True, 'turnstile_site_key': '0xABC'}):
            self.assertEqual(turnstile_site_key(), '0xABC')
