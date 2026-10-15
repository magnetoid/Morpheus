"""The webhook payload encoder names a model without touching the database.

`fire()` serializes every event's kwargs before it knows whether any endpoint
listens, so the encoder runs on every product view. Reading a field a view
deferred with `.only()` cost a query each time, and on a row deleted meanwhile
it raised DoesNotExist out of `fire()`, skipping every local subscriber.
"""

from __future__ import annotations

from django.test import TestCase

from core.hooks import hook_registry
from core.models import WebhookEndpoint


def _endpoint():
    return WebhookEndpoint.objects.create(name='n', url='https://example.com/h', events=[])


class WebhookEncoderTests(TestCase):
    def test_a_deferred_field_costs_no_query(self):
        ep = _endpoint()
        loaded = WebhookEndpoint.objects.only('id').get(pk=ep.pk)
        with self.assertNumQueries(0):
            out = hook_registry._serialize_payload({'ep': loaded})
        self.assertEqual(out['ep'], {'id': str(ep.pk), 'model': 'WebhookEndpoint'})

    def test_a_loaded_model_carries_its_identifying_fields(self):
        out = hook_registry._serialize_payload({'ep': _endpoint()})
        self.assertEqual(out['ep']['name'], 'n')

    def test_a_row_deleted_meanwhile_does_not_raise(self):
        ep = _endpoint()
        loaded = WebhookEndpoint.objects.only('id').get(pk=ep.pk)
        WebhookEndpoint.objects.filter(pk=ep.pk).delete()
        out = hook_registry._serialize_payload({'ep': loaded})
        self.assertEqual(out['ep']['model'], 'WebhookEndpoint')
