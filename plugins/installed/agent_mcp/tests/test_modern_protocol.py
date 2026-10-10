"""MCP 2026-07-28 — the stateless, per-request era, served next to the legacy
``initialize`` handshake (a dual-era server, spec §Versioning).

A modern request carries ``MCP-Protocol-Version`` / ``Mcp-Method`` /
``Mcp-Name`` headers that mirror its body, and ``_meta`` with
``io.modelcontextprotocol/protocolVersion`` + ``clientCapabilities``. The
server validates the mirror (``-32020`` HeaderMismatch, HTTP 400), refuses
versions it does not speak (``-32022``, listing ``supported``), answers
``server/discover``, stamps every result with ``resultType`` and its
``serverInfo``, and makes list/read results cacheable (``ttlMs`` +
``cacheScope``). A legacy client that opens with ``initialize`` is served
exactly as before.
"""

from __future__ import annotations

import base64
import json
from unittest import mock

from django.test import Client, TestCase

URL = '/mcp/v1/'
VERSION = '2026-07-28'
META = {
    'io.modelcontextprotocol/protocolVersion': VERSION,
    'io.modelcontextprotocol/clientCapabilities': {},
    'io.modelcontextprotocol/clientInfo': {'name': 'test-agent', 'version': '1.0'},
}


def _headers(method: str, name: str | None = None, version: str = VERSION, **extra) -> dict:
    h = {
        'HTTP_MCP_PROTOCOL_VERSION': version,
        'HTTP_MCP_METHOD': method,
        'HTTP_ACCEPT': 'application/json, text/event-stream',
    }
    if name is not None:
        h['HTTP_MCP_NAME'] = name
    h.update(extra)
    return h


def _body(method: str, params: dict | None = None, _id=1, meta: dict | None = None) -> str:
    p = dict(params or {})
    p['_meta'] = META if meta is None else meta
    msg = {'jsonrpc': '2.0', 'method': method, 'params': p}
    if _id is not None:
        msg['id'] = _id
    return json.dumps(msg)


def _post(body: str, headers: dict, token: str = ''):
    if token:
        headers = {**headers, 'HTTP_AUTHORIZATION': f'Bearer {token}'}
    return Client().post(URL, body, content_type='application/json', **headers)


class DiscoverTests(TestCase):
    def test_server_discover_answers_with_versions_capabilities_and_identity(self):
        r = _post(_body('server/discover'), _headers('server/discover'))
        self.assertEqual(r.status_code, 200)
        result = r.json()['result']
        self.assertEqual(result['resultType'], 'complete')
        self.assertIn(VERSION, result['supportedVersions'])
        self.assertIn('2024-11-05', result['supportedVersions'])
        self.assertIn('tools', result['capabilities'])
        info = result['_meta']['io.modelcontextprotocol/serverInfo']
        self.assertTrue(info['name'])
        self.assertTrue(info['version'])
        self.assertIsInstance(result['ttlMs'], int)
        self.assertEqual(result['cacheScope'], 'public')
        self.assertNotIn('Mcp-Session-Id', r)

    def test_discover_also_answers_a_legacy_probe_without_headers(self):
        r = Client().post(
            URL,
            json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'server/discover'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn(VERSION, r.json()['result']['supportedVersions'])


class ResultShapeTests(TestCase):
    def test_tools_list_is_cacheable_and_deterministic(self):
        r = _post(_body('tools/list'), _headers('tools/list'))
        self.assertEqual(r.status_code, 200)
        result = r.json()['result']
        self.assertEqual(result['resultType'], 'complete')
        self.assertIn('io.modelcontextprotocol/serverInfo', result['_meta'])
        self.assertIsInstance(result['ttlMs'], int)
        self.assertIn(result['cacheScope'], ('public', 'private'))
        names = [t['name'] for t in result['tools']]
        self.assertEqual(names, sorted(names))
        self.assertTrue(names)

    def test_resources_list_and_read_are_cacheable(self):
        r = _post(_body('resources/list'), _headers('resources/list'))
        result = r.json()['result']
        self.assertEqual(result['resultType'], 'complete')
        self.assertIn('ttlMs', result)
        self.assertIn('cacheScope', result)

    def test_a_notification_is_accepted_with_no_body(self):
        r = _post(_body('notifications/cancelled', _id=None), _headers('notifications/cancelled'))
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.content, b'')

    def test_a_modern_request_never_gets_a_session(self):
        r = _post(
            _body('tools/list'),
            _headers('tools/list', HTTP_MCP_SESSION_ID='stale-session-from-2025'),
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('Mcp-Session-Id', r)

    def test_batches_are_not_accepted_in_the_modern_era(self):
        body = json.dumps(
            [json.loads(_body('tools/list', _id=1)), json.loads(_body('tools/list', _id=2))]
        )
        r = _post(body, _headers('tools/list'))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error']['code'], -32600)


class ValidationTests(TestCase):
    def test_a_method_header_that_disagrees_with_the_body_is_a_header_mismatch(self):
        r = _post(_body('tools/list'), _headers('tools/call'))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error']['code'], -32020)

    def test_tools_call_without_mcp_name_is_a_header_mismatch(self):
        r = _post(
            _body('tools/call', {'name': 'products.search', 'arguments': {}}),
            _headers('tools/call'),
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error']['code'], -32020)

    def test_a_version_header_that_disagrees_with_meta_is_a_header_mismatch(self):
        r = _post(_body('tools/list'), _headers('tools/list', version='2025-11-25'))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error']['code'], -32020)

    def test_a_base64_sentinel_name_is_decoded_before_comparison(self):
        encoded = '=?base64?' + base64.b64encode(b'products.search').decode() + '?='
        r = _post(
            _body('tools/call', {'name': 'products.search', 'arguments': {}}),
            _headers('tools/call', name=encoded),
        )
        # Past the header check: the next gate is authentication, not -32020.
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(r.json()['error']['code'], -32020)

    def test_an_unsupported_version_lists_the_supported_ones(self):
        meta = {**META, 'io.modelcontextprotocol/protocolVersion': '2027-01-01'}
        r = _post(_body('tools/list', meta=meta), _headers('tools/list', version='2027-01-01'))
        self.assertEqual(r.status_code, 400)
        err = r.json()['error']
        self.assertEqual(err['code'], -32022)
        self.assertIn(VERSION, err['data']['supported'])
        self.assertEqual(err['data']['requested'], '2027-01-01')

    def test_missing_client_capabilities_is_invalid_params(self):
        meta = {'io.modelcontextprotocol/protocolVersion': VERSION}
        r = _post(_body('tools/list', meta=meta), _headers('tools/list'))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error']['code'], -32602)

    def test_unknown_methods_are_404_in_the_modern_era(self):
        for method in ('initialize', 'ping', 'nonsense/method'):
            with self.subTest(method=method):
                r = _post(_body(method), _headers(method))
                self.assertEqual(r.status_code, 404)
                self.assertEqual(r.json()['error']['code'], -32601)

    def test_a_foreign_origin_is_refused(self):
        r = _post(_body('tools/list'), _headers('tools/list', HTTP_ORIGIN='https://evil.example'))
        self.assertEqual(r.status_code, 403)


class ToolCallTests(TestCase):
    def setUp(self):
        from plugins.models import PluginConfig

        PluginConfig.objects.update_or_create(
            plugin_name='agent_mcp',
            defaults={
                'config': {'public_keys': [{'token': 'tok-cat', 'mcp_scopes': ['system.read']}]}
            },
        )

    def _call(self, name: str, arguments: dict | None = None, token: str = 'tok-cat'):
        return _post(
            _body('tools/call', {'name': name, 'arguments': arguments or {}}),
            _headers('tools/call', name=name),
            token=token,
        )

    def test_a_modern_call_returns_a_complete_result(self):
        r = self._call('products.search', {'name': 'anything'})
        self.assertEqual(r.status_code, 200)
        result = r.json()['result']
        self.assertEqual(result['resultType'], 'complete')
        self.assertFalse(result['isError'])
        self.assertEqual(result['content'][0]['type'], 'text')

    def test_a_tool_failure_is_an_error_result_not_a_legacy_code(self):
        from core.agents.tools import Tool

        with mock.patch.object(Tool, 'invoke', side_effect=RuntimeError('boom')):
            r = self._call('products.search', {'name': 'x'})
        self.assertEqual(r.status_code, 200)
        result = r.json()['result']
        self.assertTrue(result['isError'])
        self.assertEqual(result['resultType'], 'complete')
        self.assertIn('boom', result['content'][0]['text'])

    def test_authentication_errors_use_a_code_outside_the_reserved_range(self):
        r = self._call('products.search', {'name': 'x'}, token='')
        self.assertEqual(r.status_code, 200)
        code = r.json()['error']['code']
        self.assertFalse(-32099 <= code <= -32000, code)


class LegacyEraTests(TestCase):
    def test_initialize_still_negotiates_the_legacy_version(self):
        r = Client().post(
            URL,
            json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['result']['protocolVersion'], '2024-11-05')
        self.assertIn('Mcp-Session-Id', r)

    def test_legacy_results_keep_their_shape(self):
        r = Client().post(
            URL,
            json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('resultType', r.json()['result'])
