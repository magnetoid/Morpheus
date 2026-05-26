"""MCP Streamable HTTP transport — protocol-conformance smoke tests.

The Streamable HTTP transport (MCP spec 2025-03-26+) is the modern
replacement for the SSE-only transport. The contract we have to honour
on /mcp/v1/:

  * POST + Accept: application/json → standard JSON response (default
    transport — keep the existing integrations working)
  * POST + Accept: text/event-stream → SSE-wrapped JSON-RPC payload
  * GET → 405 (we don't push server-initiated notifications)
  * After an `initialize` call, the response carries Mcp-Session-Id
    that the client can echo on subsequent calls
"""
from __future__ import annotations

import json

from django.test import Client, TestCase


class StreamableHttpTransportTests(TestCase):
    """The four behaviours that make the endpoint MCP-streamable-compliant."""

    def setUp(self):
        self.client = Client()

    def _post(self, body: dict, accept: str = 'application/json'):
        return self.client.post(
            '/mcp/v1/',
            data=json.dumps(body),
            content_type='application/json',
            HTTP_ACCEPT=accept,
        )

    def test_get_returns_405(self):
        """No server-initiated streams — GET must be Method Not Allowed
        rather than 404 (404 would tell a client the endpoint doesn't
        exist; 405 advertises it but says we don't support GET)."""
        resp = self.client.get('/mcp/v1/')
        self.assertEqual(resp.status_code, 405)

    def test_post_json_is_default(self):
        """Default Accept (application/json) → JsonResponse, unchanged
        from the legacy behaviour — no integration regression."""
        resp = self._post({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'].split(';')[0], 'application/json')
        body = resp.json()
        self.assertEqual(body['jsonrpc'], '2.0')
        self.assertEqual(body['id'], 1)
        self.assertEqual(body['result'], {})

    def test_post_sse_wraps_response(self):
        """Accept: text/event-stream → response is wrapped in SSE
        framing (`data: <json>\\n\\n`) so streaming-capable clients can
        parse it identically to the SSE-only transport."""
        resp = self._post(
            {'jsonrpc': '2.0', 'id': 2, 'method': 'ping'},
            accept='text/event-stream',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp['Content-Type'].split(';')[0], 'text/event-stream',
        )
        body = resp.content.decode()
        self.assertTrue(body.startswith('data: '),
                        f'expected SSE framing, got: {body[:60]!r}')
        self.assertTrue(body.endswith('\n\n'))
        # Round-trip: strip the framing and the inner JSON must parse.
        payload = json.loads(body[len('data: '):].rstrip('\n'))
        self.assertEqual(payload['id'], 2)
        self.assertEqual(payload['result'], {})

    def test_initialize_mints_session_id(self):
        """initialize → server stamps Mcp-Session-Id so subsequent
        calls can be correlated. Spec says the client echoes it back."""
        resp = self._post({'jsonrpc': '2.0', 'id': 'init-1',
                           'method': 'initialize', 'params': {}})
        self.assertEqual(resp.status_code, 200)
        sess = resp.get('Mcp-Session-Id', '')
        self.assertTrue(sess, 'initialize response missing Mcp-Session-Id')
        # Should look like a hex UUID (32 chars), not a paste from somewhere.
        self.assertEqual(len(sess), 32)
        self.assertTrue(all(c in '0123456789abcdef' for c in sess))

    def test_ping_does_not_mint_session_id(self):
        """A regular call (no `initialize`) should NOT mint a new
        session — only `initialize` does. Otherwise every request would
        rotate the session id and break correlation."""
        resp = self._post({'jsonrpc': '2.0', 'id': 99, 'method': 'ping'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.has_header('Mcp-Session-Id'))

    def test_client_session_id_is_echoed(self):
        """If the client sends Mcp-Session-Id, the server must echo it
        back on the response so the client knows the server received it."""
        resp = self.client.post(
            '/mcp/v1/',
            data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}),
            content_type='application/json',
            HTTP_MCP_SESSION_ID='abcdef1234567890abcdef1234567890',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp['Mcp-Session-Id'], 'abcdef1234567890abcdef1234567890',
        )
