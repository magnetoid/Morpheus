"""The nightly health check verifies the sending domain's SPF and DMARC.

A store can be configured to send mail from a domain that publishes no SPF
or DMARC record, and every order email then lands in spam or is rejected —
invisibly, because sending "worked". The check resolves the sender domain's
TXT records over DNS-over-HTTPS (no new dependency, works from the container),
reports what is missing, and never raises an alarm it cannot justify: a lookup
that fails is "could not verify", not "broken".
"""

from __future__ import annotations

from unittest import mock

from django.test import TestCase, override_settings

from core.errors import health


class EmailAuthCheckTests(TestCase):
    def setUp(self):
        patcher = mock.patch.object(health, 'smtp_configured', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    @override_settings(DEFAULT_FROM_EMAIL='Shop <orders@shop.example>')
    def test_both_records_present_is_ok(self):
        records = {
            'shop.example': ['v=spf1 include:_spf.example.net -all'],
            '_dmarc.shop.example': ['v=DMARC1; p=quarantine; rua=mailto:dmarc@shop.example'],
        }
        with mock.patch.object(health, '_txt_records', side_effect=lambda n: records.get(n, [])):
            result = health._email_auth_check()
        self.assertTrue(result['ok'])
        self.assertIn('shop.example', result['detail'])

    @override_settings(DEFAULT_FROM_EMAIL='orders@shop.example')
    def test_missing_records_are_named(self):
        with mock.patch.object(health, '_txt_records', return_value=[]):
            result = health._email_auth_check()
        self.assertFalse(result['ok'])
        self.assertIn('SPF', result['detail'])
        self.assertIn('DMARC', result['detail'])
        self.assertIn('shop.example', result['detail'])

    @override_settings(DEFAULT_FROM_EMAIL='orders@shop.example')
    def test_a_failed_lookup_does_not_alarm(self):
        with mock.patch.object(health, '_txt_records', side_effect=RuntimeError('dns down')):
            result = health._email_auth_check()
        self.assertTrue(result['ok'])
        self.assertIn('could not verify', result['detail'])

    @override_settings(DEFAULT_FROM_EMAIL='orders@shop.example')
    def test_the_merchant_sender_wins_over_the_deployment_default(self):
        from core.models import StoreSettings

        row = StoreSettings.objects.first() or StoreSettings()
        row.default_from_email = 'hello@merchant.example'
        row.save()
        seen = []

        def lookup(name):
            seen.append(name)
            return []

        with mock.patch.object(health, '_txt_records', side_effect=lookup):
            health._email_auth_check()
        self.assertIn('merchant.example', seen)
        self.assertIn('_dmarc.merchant.example', seen)

    @override_settings(DEFAULT_FROM_EMAIL='orders@shop.example')
    def test_a_store_without_smtp_skips_the_check(self):
        with (
            mock.patch.object(health, 'smtp_configured', return_value=False),
            mock.patch.object(health, '_txt_records') as lookup,
        ):
            result = health._email_auth_check()
        self.assertTrue(result['ok'])
        lookup.assert_not_called()

    def test_the_check_is_part_of_the_core_checks(self):
        with mock.patch.object(health, '_txt_records', return_value=[]):
            names = [c['name'] for c in health._core_checks()]
        self.assertIn('Sender domain is authenticated (SPF, DMARC)', names)


class DohLookupTests(TestCase):
    def test_txt_records_are_read_from_the_dns_json_answer(self):
        payload = {
            'Status': 0,
            'Answer': [
                {'name': 'shop.example', 'type': 16, 'data': '"v=spf1 -all"'},
                {'name': 'shop.example', 'type': 16, 'data': '"google-site-verification=abc"'},
            ],
        }
        with mock.patch('requests.get') as get:
            get.return_value = mock.Mock(status_code=200, json=lambda: payload)
            records = health._txt_records('shop.example')
        self.assertEqual(records, ['v=spf1 -all', 'google-site-verification=abc'])
        self.assertEqual(get.call_args.kwargs['params'], {'name': 'shop.example', 'type': 'TXT'})
        self.assertEqual(get.call_args.kwargs['headers']['accept'], 'application/dns-json')
        self.assertLessEqual(get.call_args.kwargs['timeout'], 10)
