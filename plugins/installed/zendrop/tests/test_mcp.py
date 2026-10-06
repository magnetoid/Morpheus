"""The MCP client: standard JSON-RPC over POST, SSE or JSON replies, token-free errors."""

from __future__ import annotations

import json
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from plugins.installed.zendrop.services import mcp


class _Resp:
    def __init__(self, status=200, body=None, headers=None, text=''):
        self.status_code = status
        self._body = body
        self.headers = headers or {'Content-Type': 'application/json'}
        self.text = text or (json.dumps(body) if body is not None else '')

    def json(self):
        if self._body is None:
            raise ValueError('not json')
        return self._body


def _server(tools):
    """A fake Zendrop MCP server answering initialize / tools/list over JSON and SSE."""

    def post(url, json=None, headers=None, timeout=None):
        assert url == mcp.MCP_URL
        assert headers['Authorization'] == 'Bearer tok-123'
        assert 'text/event-stream' in headers['Accept']
        method = json.get('method')
        if method == 'initialize':
            return _Resp(
                body={
                    'jsonrpc': '2.0',
                    'id': 1,
                    'result': {
                        'protocolVersion': '2025-06-18',
                        'serverInfo': {'name': 'Zendrop MCP', 'version': '1.4'},
                    },
                },
                headers={'Content-Type': 'application/json', 'Mcp-Session-Id': 'sess-9'},
            )
        if method == 'notifications/initialized':
            return _Resp(status=202, body=None, text='')
        if method == 'tools/list':
            assert headers['Mcp-Session-Id'] == 'sess-9'  # the session from initialize is carried
            payload = {'jsonrpc': '2.0', 'id': 1, 'result': {'tools': tools}}
            return _Resp(
                headers={'Content-Type': 'text/event-stream'},
                text=f'event: message\ndata: {json_dumps(payload)}\n\n',
            )
        raise AssertionError(method)

    return post


def json_dumps(obj):
    return json.dumps(obj)


class McpClientTests(TestCase):
    def setUp(self):
        cache.clear()
        from plugins.registry import app_registry

        self.plugin = app_registry.get('zendrop')
        self.addCleanup(self.plugin.invalidate_config_cache)

    def test_list_tools_speaks_json_rpc_and_reads_an_sse_reply(self):
        tools = [
            {'name': 'list_orders', 'description': 'List and filter orders'},
            {'name': 'get_order_tracking', 'description': 'Tracking numbers for an order'},
            {'name': 'fulfill_order', 'description': 'Trigger fulfillment'},
            {'name': 'get_shipping_estimate', 'description': 'Shipping methods and costs'},
            {'name': 'get_catalog_product', 'description': 'A catalog product'},
        ]
        with mock.patch.object(mcp.requests, 'post', side_effect=_server(tools)):
            listing = mcp.list_tools('tok-123')
        self.assertEqual(listing['server']['name'], 'Zendrop MCP')
        self.assertEqual([t['name'] for t in listing['tools']], [t['name'] for t in tools])
        caps = mcp.capabilities(listing['tools'])
        self.assertIn('list_orders', caps['orders_read'])
        self.assertIn('get_order_tracking', caps['orders_read'])
        self.assertIn('fulfill_order', caps['orders_write'])
        self.assertIn('get_shipping_estimate', caps['shipping'])
        self.assertIn('get_catalog_product', caps['catalog'])

    def test_a_rejected_token_is_a_clear_error_without_the_token_in_it(self):
        with (
            mock.patch.object(
                mcp.requests,
                'post',
                return_value=_Resp(status=401, body={'message': 'Unauthenticated.'}),
            ),
            self.assertRaises(mcp.McpError) as ctx,
        ):
            mcp.list_tools('tok-SECRET')
        self.assertIn('401', str(ctx.exception))
        self.assertNotIn('tok-SECRET', str(ctx.exception))

    def test_a_json_rpc_error_is_surfaced(self):
        body = {'jsonrpc': '2.0', 'id': 1, 'error': {'code': -32601, 'message': 'Method not found'}}
        with (
            mock.patch.object(mcp.requests, 'post', return_value=_Resp(body=body)),
            self.assertRaises(mcp.McpError) as ctx,
        ):
            mcp.rpc('tools/list', token='tok-123')
        self.assertIn('Method not found', str(ctx.exception))

    def test_connection_test_without_a_token_says_so_and_caches_nothing(self):
        snapshot = mcp.test_connection()
        self.assertFalse(snapshot['ok'])
        self.assertIn('No access token', snapshot['error'])
        self.assertIsNone(mcp.cached_connection())

    def test_connection_test_caches_the_snapshot(self):
        self.plugin.set_config('access_token', 'tok-123')
        tools = [{'name': 'list_orders', 'description': ''}]
        with mock.patch.object(mcp.requests, 'post', side_effect=_server(tools)):
            snapshot = mcp.test_connection()
        self.assertTrue(snapshot['ok'])
        self.assertEqual(mcp.cached_connection()['tools'][0]['name'], 'list_orders')

    def test_network_failure_is_reported_without_raising_through_the_page(self):
        import requests

        self.plugin.set_config('access_token', 'tok-123')
        with mock.patch.object(mcp.requests, 'post', side_effect=requests.ConnectionError('boom')):
            snapshot = mcp.test_connection()
        self.assertFalse(snapshot['ok'])
        self.assertIn('Could not reach Zendrop', snapshot['error'])
