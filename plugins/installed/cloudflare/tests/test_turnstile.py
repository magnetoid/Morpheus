"""Cloudflare Turnstile — the verify helper (the forms: test_turnstile_forms.py)."""

# ruff: noqa: PLC0415
from __future__ import annotations

from unittest.mock import patch

from django.test import RequestFactory, TestCase

_CFG = 'plugins.installed.cloudflare.services._turnstile_config'


def _answer(status=200, **body):
    """A siteverify response: Cloudflare answers JSON, 200 even for a bad token."""
    from unittest.mock import MagicMock

    resp = MagicMock(status_code=status, ok=200 <= status < 300)
    resp.json.return_value = body
    return resp


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
            mp.return_value = _answer(success=True, hostname='testserver')
            self.assertTrue(verify_turnstile(req))

    def test_site_key_when_enabled(self):
        from plugins.installed.cloudflare.services import turnstile_site_key

        with patch(_CFG, return_value={'turnstile_enabled': True, 'turnstile_site_key': '0xABC'}):
            self.assertEqual(turnstile_site_key(), '0xABC')


class SpinSiteverifyTests(TestCase):
    """The server-side checks Cloudflare's Turnstile Spin wires into a backend
    (developers.cloudflare.com/turnstile/spin/, GA 2026-08-10): `success`, the
    widget's `action`, a `hostname` this store answers on (never a local one in
    production), a token of at most 2048 characters, and fail closed when
    siteverify cannot be reached. The old check read `success` alone, so a token
    solved on any site that shares the widget, or for another form, passed."""

    CFG = {'turnstile_enabled': True, 'turnstile_secret_key': 'live-secret'}

    def _verify(self, answers, *, token='tok', action='contact', host='testserver'):
        from plugins.installed.cloudflare.services import verify_turnstile

        req = RequestFactory().post('/', {'cf-turnstile-response': token}, HTTP_HOST=host)
        with (
            patch(_CFG, return_value=self.CFG),
            patch('requests.post', side_effect=answers) as post,
            patch('time.sleep'),
        ):
            return verify_turnstile(req, action=action), post

    def test_the_action_and_host_must_match(self):
        ok, post = self._verify([_answer(success=True, action='contact', hostname='testserver')])
        self.assertTrue(ok)
        sent = post.call_args.kwargs['data']
        self.assertEqual(sent['secret'], 'live-secret')
        self.assertEqual(sent['response'], 'tok')
        self.assertTrue(sent['idempotency_key'])

    def test_a_token_for_another_form_is_refused(self):
        ok, _ = self._verify([_answer(success=True, action='newsletter', hostname='testserver')])
        self.assertFalse(ok)

    def test_a_token_solved_on_another_site_is_refused(self):
        ok, _ = self._verify([_answer(success=True, action='contact', hostname='evil.example')])
        self.assertFalse(ok)

    def test_a_local_host_is_refused_in_production(self):
        ok, _ = self._verify(
            [_answer(success=True, action='contact', hostname='localhost')], host='localhost'
        )
        self.assertFalse(ok)

    def test_the_stores_own_address_is_accepted_behind_a_proxy(self):
        with patch('core.utils.site.site_base_url', return_value='https://dotbooks.store'):
            ok, _ = self._verify(
                [_answer(success=True, action='contact', hostname='dotbooks.store')],
                host='web:8000',
            )
        self.assertTrue(ok)

    def test_an_overlong_token_is_refused_without_a_call(self):
        ok, post = self._verify([], token='x' * 2049)
        self.assertFalse(ok)
        post.assert_not_called()

    def test_a_server_error_is_retried_once_with_the_same_key(self):
        ok, post = self._verify(
            [_answer(status=503), _answer(success=True, action='contact', hostname='testserver')]
        )
        self.assertTrue(ok)
        keys = {c.kwargs['data']['idempotency_key'] for c in post.call_args_list}
        self.assertEqual((post.call_count, len(keys)), (2, 1))

    def test_an_unreachable_siteverify_fails_closed(self):
        import requests

        ok, post = self._verify([requests.ConnectionError('down'), requests.Timeout('slow')])
        self.assertFalse(ok)
        self.assertEqual(post.call_count, 2)

    def test_a_test_secret_skips_the_host_check(self):
        self.CFG = {**self.CFG, 'turnstile_secret_key': '1x0000000000000000000000000000000AA'}
        ok, _ = self._verify([_answer(success=True, action='contact', hostname='example.com')])
        self.assertTrue(ok)

    def test_the_widget_and_the_check_name_the_same_action(self):
        from plugins.installed.cloudflare import services

        cfg = {**self.CFG, 'turnstile_site_key': 'site', 'turnstile_sign_in': True}
        req = RequestFactory().post('/', {'cf-turnstile-response': 'tok'})
        with (
            patch(_CFG, return_value=cfg),
            patch.object(services, 'verify_turnstile', return_value=True) as verify,
        ):
            html = services.turnstile_widget('', 'sign_in', {'request': req})
            services.turnstile_passes(True, request=req, form='sign_in')
        self.assertIn('data-action="sign-in"', html)
        self.assertEqual(verify.call_args.kwargs['action'], 'sign-in')


class TurnstileHealthTests(TestCase):
    def _health(self, cfg, answers=()):
        from plugins.installed.cloudflare.services import turnstile_health

        with (
            patch(_CFG, return_value=cfg),
            patch('requests.post', side_effect=list(answers)),
            patch('time.sleep'),
        ):
            return turnstile_health([])

    ON = {'turnstile_enabled': True, 'turnstile_site_key': 'site', 'turnstile_secret_key': 'live'}

    def test_off_adds_no_check(self):
        self.assertEqual(self._health({}), [])

    def test_a_working_secret_passes(self):
        [check] = self._health(
            self.ON, [_answer(success=False, **{'error-codes': ['invalid-input-response']})]
        )
        self.assertTrue(check['ok'], check)

    def test_a_refused_secret_fails(self):
        [check] = self._health(
            self.ON, [_answer(success=False, **{'error-codes': ['invalid-input-secret']})]
        )
        self.assertFalse(check['ok'], check)

    def test_a_test_secret_fails_without_a_call(self):
        cfg = {**self.ON, 'turnstile_secret_key': '1x0000000000000000000000000000000AA'}
        [check] = self._health(cfg)
        self.assertFalse(check['ok'])
        self.assertIn('test key', check['detail'])
