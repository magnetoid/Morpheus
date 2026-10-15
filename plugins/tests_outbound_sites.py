"""Every staff-entered URL the server calls goes through core.net.outbound_request."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase


class OutboundSitesTests(TestCase):
    def test_a_workflow_cannot_post_to_the_private_network(self):
        from plugins.installed.workflows.engine import _action_webhook_post

        with patch('requests.post') as post:
            ok, msg = _action_webhook_post({'url': 'http://169.254.169.254/latest'}, {})
        self.assertFalse(ok)
        self.assertIn('not a public address', msg)
        post.assert_not_called()

    def test_the_feed_push_refuses_a_private_endpoint(self):
        from plugins.installed.openai_shopping.tasks import push_feed
        from plugins.registry import app_registry

        plugin = app_registry.get('openai_shopping')
        plugin.set_config('push_endpoint', 'https://127.0.0.1/ingest')
        plugin.set_config('push_token', 't')
        self.addCleanup(plugin.set_config, 'push_endpoint', '')
        self.addCleanup(plugin.set_config, 'push_token', '')
        with patch('requests.post') as post:
            result = push_feed()
        self.assertFalse(result['pushed'])
        post.assert_not_called()

    def test_the_woocommerce_importer_refuses_a_private_store(self):
        from core.net import UnsafeUrlError
        from plugins.installed.importers.adapters.woocommerce import _HTTPClient

        client = _HTTPClient(base_url='http://192.168.1.10', consumer_key='k', consumer_secret='s')
        with patch('requests.get') as get, self.assertRaises(UnsafeUrlError) as cm:
            client.get('products')
        get.assert_not_called()
        self.assertIn('not a public address', str(cm.exception))
