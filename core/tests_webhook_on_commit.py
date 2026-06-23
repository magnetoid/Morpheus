"""Webhook dispatch is deferred to ``transaction.on_commit`` so a request that
rolls back never emits a phantom webhook (regression for
``core.hooks.HookRegistry._dispatch_remote``)."""

# ruff: noqa: PLC0415
from __future__ import annotations

from unittest import mock

from django.db import transaction
from django.test import TestCase


class WebhookOnCommitTests(TestCase):
    def _endpoint(self):
        from core.models import WebhookEndpoint

        return WebhookEndpoint.objects.create(
            name='t',
            url='https://example.com/hook',
            secret='s',
            events=['test.event'],
            is_active=True,
        )

    def test_dispatch_runs_after_commit(self):
        from core.hooks import hook_registry

        self._endpoint()
        with mock.patch('core.tasks.dispatch_webhook.delay') as delay:
            with self.captureOnCommitCallbacks(execute=True):
                hook_registry.fire('test.event', foo='bar')
            delay.assert_called_once()

    def test_no_dispatch_when_transaction_rolls_back(self):
        from core.hooks import hook_registry

        self._endpoint()
        with mock.patch('core.tasks.dispatch_webhook.delay') as delay:
            try:
                with transaction.atomic():
                    hook_registry.fire('test.event', foo='bar')
                    raise RuntimeError('force rollback')
            except RuntimeError:
                pass
            delay.assert_not_called()
