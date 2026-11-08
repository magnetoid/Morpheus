"""Turnstile on every public form (owner, 2026-11-08).

dotbooks asked for its contact forms and sign-in pages behind Turnstile, not the
checkout. Each kind of form is a switch on the Cloudflare app (`turnstile_contact`,
`turnstile_newsletter`, `turnstile_sign_in`, `turnstile_affiliates`); a protected form
shows the widget and its view refuses a POST without a valid token, before it writes,
emails or signs anyone in.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import re
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from themes.test_head_contract import _activate_theme

_ON = {
    'turnstile_enabled': True,
    'turnstile_site_key': '0x4AAAAAAATEST',
    'turnstile_secret_key': '0x4AAAAAAATESTSECRET',
}
_GOOD = {'cf-turnstile-response': 'good-token'}


def _siteverify(url, data=None, timeout=None):
    # Any form's action: these tests are about which forms ask; the action and
    # hostname checks themselves are in test_turnstile.SpinSiteverifyTests.
    answer = mock.Mock(status_code=200, ok=True)
    answer.json.return_value = {
        'success': data.get('response') == 'good-token',
        'action': mock.ANY,
        'hostname': 'testserver',
    }
    return answer


@override_settings(ACCOUNT_RATE_LIMITS=False)
class TurnstileFormTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        from plugins.registry import app_registry

        cache.clear()
        _activate_theme(self, 'dot_books')
        self.app = app_registry.get('cloudflare')
        self.configure(**_ON)
        patcher = mock.patch('requests.post', side_effect=_siteverify)
        self.siteverify = patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def crm():
        # The contact form files a lead and logs the message on it.
        from contextlib import ExitStack, contextmanager

        @contextmanager
        def both():
            with ExitStack() as stack:
                upsert = stack.enter_context(
                    mock.patch('plugins.installed.crm.services.upsert_lead')
                )
                stack.enter_context(mock.patch('plugins.installed.crm.services.log_interaction'))
                yield upsert

        return both()

    def configure(self, **values):
        for key, value in values.items():
            self.app.set_config(key, value)
        self.app.invalidate_config_cache()
        self.addCleanup(self.app.invalidate_config_cache)

    # ── The widget ─────────────────────────────────────────────────────────
    def test_every_protected_page_shows_the_widget_and_loads_the_script_once(self):
        pages = {
            '/contact/': 'contact',
            '/do-not-sell/': 'contact',
            '/auth/login/': 'sign-in',
            '/auth/signup/': 'sign-in',
            '/auth/password/reset/': 'sign-in',
            '/auth/otp/': 'sign-in',
        }
        for path, action in pages.items():
            with self.subTest(path=path):
                html = self.client.get(path).content.decode()
                self.assertIn(f'data-action="{action}"', html)
                # The footer's newsletter form is on every page too.
                self.assertIn('data-action="newsletter"', html)
                self.assertEqual(html.count('challenges.cloudflare.com/turnstile/v0/api.js'), 1)

    def test_a_switched_off_kind_shows_no_widget_and_asks_nothing(self):
        self.configure(turnstile_contact=False)
        html = self.client.get('/contact/').content.decode()
        self.assertNotIn('data-action="contact"', html)
        with self.crm() as upsert:
            self.client.post('/contact/', {'email': 'a@example.com', 'message': 'Hi'})
        upsert.assert_called_once()

    def test_without_both_keys_nothing_is_protected(self):
        # A widget that cannot verify would refuse every real visitor.
        self.configure(turnstile_secret_key='')
        self.assertNotIn('class="cf-turnstile"', self.client.get('/contact/').content.decode())
        resp = self.client.post('/newsletter/subscribe/', {'email': 'a@example.com'})
        self.assertEqual(resp.status_code, 200)

    # ── The checks ────────────────────────────────────────────────────────
    def test_the_contact_form(self):
        with self.crm() as upsert:
            resp = self.client.post('/contact/', {'email': 'a@example.com', 'message': 'Hi'})
            self.assertContains(resp, 'not a robot')
            upsert.assert_not_called()
            self.client.post('/contact/', {'email': 'a@example.com', 'message': 'Hi', **_GOOD})
            upsert.assert_called_once()

    def test_do_not_sell(self):
        with mock.patch('plugins.installed.consent.services.write_consent') as write:
            self.assertContains(self.client.post('/do-not-sell/', {}), 'not a robot')
            write.assert_not_called()
            self.client.post('/do-not-sell/', _GOOD)
            write.assert_called_once()

    def test_newsletter(self):
        from plugins.installed.newsletter.models import NewsletterSubscriber

        resp = self.client.post('/newsletter/subscribe/', {'email': 'a@example.com'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('not a robot', resp.json()['error'])
        self.assertFalse(NewsletterSubscriber.objects.exists())
        resp = self.client.post('/newsletter/subscribe/', {'email': 'a@example.com', **_GOOD})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(NewsletterSubscriber.objects.filter(email='a@example.com').exists())

    def test_a_cms_form(self):
        from plugins.installed.cms.models import Form

        Form.objects.create(key='ask', label='Ask', is_active=True)
        with mock.patch('plugins.installed.cms.services.submit_form') as submit:
            self.client.post('/forms/ask/submit/', {'email': 'a@example.com'})
            submit.assert_not_called()
            self.client.post('/forms/ask/submit/', {'email': 'a@example.com', **_GOOD})
            submit.assert_called_once()

    def test_the_emailed_sign_in_code(self):
        resp = self.client.post('/auth/otp/', {'email': 'a@example.com'})
        self.assertContains(resp, 'not a robot')
        self.assertEqual(len(mail.outbox), 0)
        resp = self.client.post('/auth/otp/', {'email': 'a@example.com', **_GOOD})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_sign_in_with_a_password(self):
        get_user_model().objects.create_user(
            username='reader', email='reader@example.com', password='a-long-pass-phrase'
        )
        creds = {'login': 'reader@example.com', 'password': 'a-long-pass-phrase'}
        resp = self.client.post('/auth/login/', creds)
        self.assertRedirects(resp, '/auth/login/', fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.client.post('/auth/login/', {**creds, **_GOOD})
        self.assertIn('_auth_user_id', self.client.session)

    def test_sign_up(self):
        form = {
            'email': 'new@example.com',
            'password1': 'a-long-pass-phrase',
            'password2': 'a-long-pass-phrase',
        }
        self.client.post('/auth/signup/', form)
        self.assertFalse(get_user_model().objects.filter(email='new@example.com').exists())
        self.client.post('/auth/signup/', {**form, **_GOOD})
        self.assertTrue(get_user_model().objects.filter(email='new@example.com').exists())

    def test_password_reset(self):
        get_user_model().objects.create_user(
            username='reader', email='reader@example.com', password='a-long-pass-phrase'
        )
        self.client.post('/auth/password/reset/', {'email': 'reader@example.com'})
        self.assertEqual(len(mail.outbox), 0)
        self.client.post('/auth/password/reset/', {'email': 'reader@example.com', **_GOOD})
        self.assertEqual(len(mail.outbox), 1)

    def test_a_forged_token_is_refused(self):
        resp = self.client.post(
            '/newsletter/subscribe/', {'email': 'a@example.com', 'cf-turnstile-response': 'forged'}
        )
        self.assertEqual(resp.status_code, 400)
        # The secret went to Cloudflare's siteverify, never anywhere else.
        url = self.siteverify.call_args.args[0]
        self.assertTrue(
            re.match(r'^https://challenges\.cloudflare\.com/turnstile/v0/siteverify$', url)
        )
