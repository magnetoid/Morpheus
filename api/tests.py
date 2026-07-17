import json

from django.test import TestCase


class GraphQLAgentAuthTests(TestCase):
    def test_graphql_agent_requires_bearer_token(self):
        resp = self.client.post(
            '/graphql/agent/',
            data=json.dumps({'query': '{ ping }'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 401)

    def test_graphql_agent_accepts_valid_api_key(self):
        from core.models import APIKey, StoreChannel

        channel = StoreChannel.objects.create(name='Default', domain='example.test')
        api_key = APIKey.objects.create(
            name='Test Agent',
            scopes=['read:products'],
            channel=channel,
        )

        resp = self.client.post(
            '/graphql/agent/',
            data=json.dumps({'query': '{ ping }'}),
            content_type='application/json',
            # Tokens are stored hashed; the raw value is exposed once at creation.
            HTTP_AUTHORIZATION=f'Bearer {api_key._raw_key}',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get('data', {}).get('ping'), 'pong')


class WebhookSignatureTests(TestCase):
    """The HMAC helper must produce stable, verifiable signatures."""

    def test_signature_round_trips(self):
        from core.tasks import _canonical_payload, compute_hmac_signature, verify_hmac_signature

        secret = 's3cret'
        payload = {'b': 2, 'a': 1, 'list': [1, 2, 3]}
        sig = compute_hmac_signature(secret, payload)
        self.assertTrue(verify_hmac_signature(secret, _canonical_payload(payload), sig))

    def test_signature_rejects_tampered_payload(self):
        from core.tasks import _canonical_payload, compute_hmac_signature, verify_hmac_signature

        secret = 's3cret'
        sig = compute_hmac_signature(secret, {'a': 1})
        self.assertFalse(verify_hmac_signature(secret, _canonical_payload({'a': 2}), sig))

    def test_signature_rejects_wrong_secret(self):
        from core.tasks import _canonical_payload, compute_hmac_signature, verify_hmac_signature

        sig = compute_hmac_signature('right', {'a': 1})
        self.assertFalse(verify_hmac_signature('wrong', _canonical_payload({'a': 1}), sig))


class GraphQLDepthLimitTests(TestCase):
    def test_depth_limit_rejects_deeply_nested_query(self):
        # Build a query that nests deeper than GRAPHQL_MAX_QUERY_DEPTH.
        depth = 30
        nested = '{ ping }'
        for _ in range(depth):
            nested = '{ a ' + nested + ' }'
        resp = self.client.post(
            '/graphql/',
            data=json.dumps({'query': nested}),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, (400, 422))


class RestPermissionTests(TestCase):
    """REST defaults: products are public, orders require auth."""

    def test_products_are_public(self):
        resp = self.client.get('/v1/products/')
        self.assertIn(resp.status_code, (200, 301, 302))

    def test_orders_require_auth(self):
        resp = self.client.get('/v1/orders/')
        # DRF returns 401 with WWW-Authenticate, 403 otherwise.
        self.assertIn(resp.status_code, (401, 403))

    def test_legacy_rest_alias_removed(self):
        # The /rest/ duplicate of v1 should no longer exist.
        resp = self.client.get('/rest/products/')
        self.assertEqual(resp.status_code, 404)


class RequestIdMiddlewareTests(TestCase):
    """Every response carries an X-Request-ID header (generated or echoed)."""

    def test_response_carries_generated_request_id(self):
        resp = self.client.get('/healthz')
        self.assertIn('X-Request-ID', resp.headers)
        self.assertGreaterEqual(len(resp.headers['X-Request-ID']), 16)

    def test_response_echoes_inbound_request_id(self):
        resp = self.client.get('/healthz', HTTP_X_REQUEST_ID='caller-rid-123')
        self.assertEqual(resp.headers['X-Request-ID'], 'caller-rid-123')


class JsonFormatterTests(TestCase):
    def test_json_formatter_emits_required_fields(self):
        import json as _json
        import logging

        from core.log_formatters import JsonFormatter
        from core.request_id import _request_id_ctx

        token = _request_id_ctx.set('rid-test-1')
        try:
            rec = logging.LogRecord(
                name='morph.test',
                level=logging.INFO,
                pathname='',
                lineno=1,
                msg='hello %s',
                args=('world',),
                exc_info=None,
            )
            from core.request_id import RequestIdFilter

            RequestIdFilter().filter(rec)
            payload = _json.loads(JsonFormatter().format(rec))
            self.assertEqual(payload['msg'], 'hello world')
            self.assertEqual(payload['level'], 'INFO')
            self.assertEqual(payload['request_id'], 'rid-test-1')
        finally:
            _request_id_ctx.reset(token)


class SentryScrubberTests(TestCase):
    def test_before_send_scrubs_auth_headers_and_password(self):
        from core.sentry import _before_send

        event = {
            'request': {
                'headers': {
                    'Authorization': 'Bearer SECRET',
                    'X-Agent-Token': 'tok',
                    'User-Agent': 'curl/8',
                },
                'data': {'username': 'u', 'password': 'p', 'card_number': '4242424242424242'},
                'cookies': 'sessionid=abc',
            },
            'extra': {'api_key': 'leak'},
        }
        out = _before_send(event, hint={})
        self.assertEqual(out['request']['headers']['Authorization'], '[scrubbed]')
        self.assertEqual(out['request']['headers']['X-Agent-Token'], '[scrubbed]')
        self.assertEqual(out['request']['headers']['User-Agent'], 'curl/8')
        self.assertEqual(out['request']['data']['password'], '[scrubbed]')
        self.assertEqual(out['request']['data']['card_number'], '[scrubbed]')
        self.assertEqual(out['request']['data']['username'], 'u')
        self.assertEqual(out['request']['cookies'], '[scrubbed]')
        self.assertEqual(out['extra']['api_key'], '[scrubbed]')


class DRFExceptionHandlerTests(TestCase):
    def test_unhandled_drf_exception_returns_envelope(self):
        from unittest.mock import MagicMock

        from rest_framework.exceptions import NotAuthenticated

        from api.exception_handler import morpheus_exception_handler

        # NotAuthenticated -> DRF default handler returns a 401, our wrapper repackages it.
        ctx = {'view': MagicMock(), 'args': (), 'kwargs': {}, 'request': MagicMock()}
        resp = morpheus_exception_handler(NotAuthenticated('nope'), ctx)
        self.assertEqual(resp.status_code, 401)
        body = resp.data
        self.assertEqual(body['status'], 'error')
        self.assertEqual(body['code'], 'NotAuthenticated')
        self.assertIn('request_id', body)


class ReadyzTests(TestCase):
    def test_readyz_reports_version_for_deploy_smoke(self):
        # scripts/deploy_smoke.sh asserts this key to confirm production
        # converged on the pushed commit — removing it breaks the deploy gate.
        from django.conf import settings

        resp = self.client.get('/readyz')
        self.assertIn(resp.status_code, (200, 503))  # 503 = degraded, still JSON
        data = resp.json()
        self.assertEqual(data['version'], settings.MORPHEUS_VERSION)
        self.assertIn(data['status'], ('ok', 'degraded'))
        self.assertIn('checks', data)
