"""The merchant's sender address applies to every email the store sends.

`StoreSettings.default_from_email` used to reach mail only as a side effect:
constructing `MorpheusEmailBackend` overwrote `settings.DEFAULT_FROM_EMAIL`.
Callers read that setting while *building* a message — usually before any
backend exists in the process, and async mail is built in the web process and
sent by the worker — so live newsletter confirmations went out from the
deployment's fallback (`noreply@…`, a mailbox that does not exist) while the
merchant had chosen `hello@…`.
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
        row.save()

    def _send(self, message) -> str:
        out = io.StringIO()
        MorpheusEmailBackend(stream=out).send_messages([message])
        return out.getvalue()

    def test_a_message_built_before_the_backend_uses_the_merchant_sender(self):
        message = EmailMessage('Hi', 'Body', None, ['a@example.com'])
        sent = self._send(message)
        self.assertEqual(message.from_email, 'hello@shop.test')
        self.assertIn('From: hello@shop.test', sent)

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
        self.assertEqual(message.from_email, 'noreply@example.com')
