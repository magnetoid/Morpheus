"""A merchant webhook is posted once, after commit, in one body shape.

Core's dispatcher and webhooks_ui's fan-out both posted every subscribed event,
in two shapes; the fan-out enqueued during the hook, so it could post before the
transaction committed, or for one that rolled back, and it ignored '*'. Core is
now the only trigger; webhooks_ui takes the delivery (log, retries, replay)
through the WEBHOOK_DELIVER filter.
"""

from __future__ import annotations

import json
from unittest import mock

from django.db import transaction
from django.test import TestCase

from core.hooks import hook_registry
from core.models import WebhookEndpoint
from core.tasks import _canonical_payload
from plugins.installed.webhooks_ui.models import WebhookDelivery
from plugins.installed.webhooks_ui.tasks import deliver_webhook
from plugins.registry import app_registry

_UI = 'plugins.installed.webhooks_ui.tasks.deliver_webhook.delay'
_CORE = 'core.tasks.dispatch_webhook.delay'
# An event no app subscribes to: the test exercises delivery, not order handlers.
EVENT = 'test.webhook.event'


def _endpoint(events):
    return WebhookEndpoint.objects.create(
        name='t', url='https://example.com/hook', secret='s', events=events, is_active=True
    )


class OneTriggerTests(TestCase):
    def test_one_delivery_through_webhooks_ui_and_none_from_core(self):
        _endpoint([EVENT])
        with (
            mock.patch(_UI) as ui,
            mock.patch(_CORE) as core,
            self.captureOnCommitCallbacks(execute=True),
        ):
            hook_registry.fire(EVENT, foo='bar')
        self.assertEqual(ui.call_count, 1)
        core.assert_not_called()
        self.assertEqual(WebhookDelivery.objects.get().payload, {'foo': 'bar'})

    def test_nothing_is_sent_when_the_transaction_rolls_back(self):
        _endpoint([EVENT])
        with mock.patch(_UI) as ui, mock.patch(_CORE) as core:
            try:
                with transaction.atomic():
                    hook_registry.fire(EVENT, foo='bar')
                    raise RuntimeError('rollback')
            except RuntimeError:
                pass
        ui.assert_not_called()
        core.assert_not_called()
        self.assertFalse(WebhookDelivery.objects.exists())

    def test_an_all_events_endpoint_reaches_the_log(self):
        _endpoint(['*'])
        with mock.patch(_UI), self.captureOnCommitCallbacks(execute=True):
            hook_registry.fire('test.webhook.other', foo=1)
        self.assertEqual(WebhookDelivery.objects.get().event_name, 'test.webhook.other')

    def test_with_webhooks_ui_off_core_posts_once(self):
        self.addCleanup(app_registry.activate, 'webhooks_ui')
        app_registry.deactivate('webhooks_ui')
        _endpoint([EVENT])
        with mock.patch(_CORE) as core, self.captureOnCommitCallbacks(execute=True):
            hook_registry.fire(EVENT, foo='bar')
        self.assertEqual(core.call_count, 1)

    def test_if_webhooks_ui_cannot_enqueue_core_still_posts(self):
        # Review Focus 3: a broken delivery owner must not lose the event.
        _endpoint([EVENT])
        with (
            mock.patch(
                'plugins.installed.webhooks_ui.services.enqueue_delivery',
                side_effect=RuntimeError('db down'),
            ),
            mock.patch(_CORE) as core,
            self.captureOnCommitCallbacks(execute=True),
        ):
            hook_registry.fire(EVENT, foo='bar')
        self.assertEqual(core.call_count, 1)

    def test_the_body_is_cores_canonical_payload(self):
        ep = _endpoint(['order.placed'])
        d = WebhookDelivery.objects.create(
            endpoint=ep, event_name='order.placed', payload={'b': 1, 'a': 2}
        )
        with (
            mock.patch('requests.post') as post,
            mock.patch('core.net.is_safe_remote_host', return_value=True),
        ):
            post.return_value = mock.Mock(status_code=200, text='ok')
            deliver_webhook(str(d.id))
        self.assertEqual(post.call_args.kwargs['data'], _canonical_payload({'b': 1, 'a': 2}))
        self.assertIs(post.call_args.kwargs['allow_redirects'], False)
        self.assertEqual(json.loads(post.call_args.kwargs['data']), {'a': 2, 'b': 1})
