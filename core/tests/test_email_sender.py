"""The merchant's sender address applies to every email the store sends.

`StoreSettings.default_from_email` used to reach mail only as a side effect:
constructing `MorpheusEmailBackend` overwrote `settings.DEFAULT_FROM_EMAIL`.
Callers read that setting while *building* a message — usually before any
backend exists in the process, and async mail is built in the web process and
sent by the worker — so live newsletter confirmations went out from the
deployment's fallback (`noreply@…`, a mailbox that does not exist) while the
merchant had chosen `hello@…`.

A bare address is shown by its local part, so every email read "hello" in the
inbox: the store's name now goes beside the store's own address.
"""

from __future__ import annotations

import io

from django.conf import settings
from django.core.mail import EmailMessage
from django.test import TestCase, override_settings

from core.email import MorpheusEmailBackend
from core.models import StoreSettings


@override_settings(EMAIL_HOST='', DEFAULT_FROM_EMAIL='noreply@example.com')
class MerchantSenderTests(TestCase):
    def setUp(self):
        row = StoreSettings.objects.first() or StoreSettings.objects.create()
        row.default_from_email = 'hello@shop.test'
        row.store_name = 'Dot Books'
        row.save()

    def _send(self, message) -> str:
        out = io.StringIO()
        MorpheusEmailBackend(stream=out).send_messages([message])
        return out.getvalue()

    def test_a_message_built_before_the_backend_uses_the_merchant_sender(self):
        message = EmailMessage('Hi', 'Body', None, ['a@example.com'])
        sent = self._send(message)
        self.assertEqual(message.from_email, 'Dot Books <hello@shop.test>')
        self.assertIn('From: Dot Books <hello@shop.test>', sent)

    def test_an_explicit_sender_is_kept(self):
        message = EmailMessage('Hi', 'Body', 'billing@shop.test', ['a@example.com'])
        self._send(message)
        self.assertEqual(message.from_email, 'billing@shop.test')

    def test_the_fallback_setting_is_not_rewritten(self):
        MorpheusEmailBackend(stream=io.StringIO())
        self.assertEqual(settings.DEFAULT_FROM_EMAIL, 'noreply@example.com')

    def test_without_a_merchant_sender_the_fallback_is_used(self):
        StoreSettings.objects.update(default_from_email='')
        message = EmailMessage('Hi', 'Body', None, ['a@example.com'])
        self._send(message)
        self.assertEqual(message.from_email, 'Dot Books <noreply@example.com>')


@override_settings(
    EMAIL_HOST='',
    DEFAULT_FROM_EMAIL='noreply@example.com',
    STORE_NAME='Morpheus Store',
    ALLOWED_HOSTS=['dotbooks.store', 'localhost'],
)
class SenderNameTests(TestCase):
    """The name beside the address is the store's, never the mailbox's."""

    def setUp(self):
        self.row = StoreSettings.objects.first() or StoreSettings.objects.create()
        self.row.default_from_email = 'hello@shop.test'
        self.row.store_name = 'Dot Books'
        self.row.save()

    def _from(self, from_email=None) -> str:
        message = EmailMessage('Hi', 'Body', from_email, ['a@example.com'])
        MorpheusEmailBackend(stream=io.StringIO()).send_messages([message])
        return message.from_email

    def _save(self, **fields):
        StoreSettings.objects.filter(pk=self.row.pk).update(**fields)

    def test_a_name_the_merchant_wrote_is_kept(self):
        self._save(default_from_email='Dot Books Team <hello@shop.test>')
        self.assertEqual(self._from(), 'Dot Books Team <hello@shop.test>')

    def test_the_merchants_own_address_written_out_gets_the_name(self):
        self.assertEqual(self._from('hello@shop.test'), 'Dot Books <hello@shop.test>')

    def test_another_address_is_left_as_written(self):
        self.assertEqual(self._from('marko@shop.test'), 'marko@shop.test')

    def test_the_default_store_name_is_not_a_name(self):
        """A store that never named itself is not "Morpheus Store": the site names it."""
        self._save(store_name='Morpheus Store')
        # A dot is quoted in a display name; the inbox shows dotbooks.store.
        self.assertEqual(self._from(), '"dotbooks.store" <hello@shop.test>')

    @override_settings(STORE_NAME='Irving Survival')
    def test_the_deployments_store_name_stands_in_for_the_default(self):
        self._save(store_name='Morpheus Store')
        self.assertEqual(self._from(), 'Irving Survival <hello@shop.test>')

    def test_a_name_with_a_comma_is_quoted(self):
        self._save(store_name='Books, Inc.')
        self.assertEqual(self._from(), '"Books, Inc." <hello@shop.test>')

    def test_a_line_break_in_the_name_never_reaches_the_header(self):
        self._save(store_name='Dot\r\nBcc: x@evil.test')
        sender = self._from()
        self.assertNotIn('\n', sender)
        self.assertEqual(sender, '"Dot Bcc: x@evil.test" <hello@shop.test>')

    def test_a_name_outside_ascii_is_encoded_in_the_header(self):
        self._save(store_name='Crna Gora — Čačak')
        message = EmailMessage('Hi', 'Body', None, ['a@example.com'])
        out = io.StringIO()
        MorpheusEmailBackend(stream=out).send_messages([message])
        self.assertEqual(message.from_email, 'Crna Gora — Čačak <hello@shop.test>')
        self.assertIn('=?utf-8?', out.getvalue().split('From: ', 1)[1].splitlines()[0])
