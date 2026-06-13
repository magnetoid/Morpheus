"""Cloudflare Turnstile — verify helper + {% turnstile %} tag."""

# ruff: noqa: PLC0415
from __future__ import annotations

from unittest.mock import patch

from django.template import Context, Template
from django.test import RequestFactory, TestCase

_CFG = 'plugins.installed.cloudflare.services._turnstile_config'
_SITE = 'plugins.installed.cloudflare.services.turnstile_site_key'


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

    def test_tag_renders_widget_when_site_key(self):
        with patch(_SITE, return_value='0xABC'):
            out = Template('{% load cloudflare %}{% turnstile %}').render(Context())
        self.assertIn('cf-turnstile', out)
        self.assertIn('0xABC', out)

    def test_tag_empty_when_disabled(self):
        with patch(_SITE, return_value=''):
            out = Template('{% load cloudflare %}{% turnstile %}').render(Context())
        self.assertNotIn('cf-turnstile', out)
