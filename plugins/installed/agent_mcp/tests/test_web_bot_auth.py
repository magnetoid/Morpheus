"""Web Bot Auth at the origin: RFC 9421 signatures verified against the agent's
published key directory, without Cloudflare in front.

The agent signs ``@authority`` (+ ``signature-agent``) with an Ed25519 key,
names the key by its RFC 7638 thumbprint in ``keyid`` and tags the signature
``web-bot-auth``; its JWKS lives at
``<Signature-Agent origin>/.well-known/http-message-signatures-directory``.
A verified request carries ``request.trusted_agent`` (provider
``web-bot-auth``) exactly like a Cloudflare-stamped one, so the order stamp
works unchanged. Everything else fails SOFT: an unverifiable request is an
anonymous request, never a refused one.
"""

from __future__ import annotations

import base64
import json
import time
from unittest import mock

from cryptography.hazmat.primitives.asymmetric import ed25519
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from plugins.installed.agent_mcp import web_bot_auth
from plugins.installed.agent_mcp.middleware import TrustedAgentMiddleware

AGENT = 'https://agent.test'


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


class _Signer:
    def __init__(self):
        self.key = ed25519.Ed25519PrivateKey.generate()
        from cryptography.hazmat.primitives import serialization

        self.x = _b64url(
            self.key.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
        )
        self.keyid = web_bot_auth.jwk_thumbprint({'kty': 'OKP', 'crv': 'Ed25519', 'x': self.x})

    def jwks(self, *, kid: bool = True) -> dict:
        key = {'kty': 'OKP', 'crv': 'Ed25519', 'x': self.x}
        if kid:
            key['kid'] = self.keyid
        return {'keys': [key]}

    def headers(
        self,
        authority: str = 'testserver',
        *,
        created: int | None = None,
        expires: int | None = None,
        tag: str = 'web-bot-auth',
        keyid: str | None = None,
        agent: str = AGENT,
        components: tuple[str, ...] = ('@authority', 'signature-agent'),
    ) -> dict:
        now = int(time.time())
        created = now - 5 if created is None else created
        expires = now + 300 if expires is None else expires
        agent_field = f'"{agent}"'
        params = (
            '(' + ' '.join(f'"{c}"' for c in components) + ')'
            f';created={created};expires={expires};keyid="{keyid or self.keyid}"'
            f';alg="ed25519";tag="{tag}"'
        )
        values = {'@authority': authority, 'signature-agent': agent_field}
        base = '\n'.join(f'"{c}": {values[c]}' for c in components)
        base += f'\n"@signature-params": {params}'
        sig = self.key.sign(base.encode('utf-8'))
        return {
            'HTTP_SIGNATURE_AGENT': agent_field,
            'HTTP_SIGNATURE_INPUT': f'sig1={params}',
            'HTTP_SIGNATURE': f'sig1=:{base64.b64encode(sig).decode("ascii")}:',
        }


def _run(headers: dict, path: str = '/mcp/storefront/v1/'):
    request = RequestFactory().get(path, **headers)
    TrustedAgentMiddleware(lambda r: HttpResponse('ok'))(request)
    return request


class ParsingTests(SimpleTestCase):
    def test_thumbprint_is_rfc7638(self):
        # RFC 8037 appendix A.3 key → the thumbprint it documents.
        jwk = {'kty': 'OKP', 'crv': 'Ed25519', 'x': '11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo'}
        self.assertEqual(
            web_bot_auth.jwk_thumbprint(jwk), 'kPrK_qmxVWaYVA9wwBF6Iuo3vVzz7TxHCTwXBygrS4k'
        )

    def test_signature_input_parses_components_and_params(self):
        label, comps, params, raw = web_bot_auth.parse_signature_input(
            'sig1=("@authority" "signature-agent");created=1;expires=2;keyid="k";alg="ed25519";tag="web-bot-auth"'
        )
        self.assertEqual(label, 'sig1')
        self.assertEqual(comps, ['@authority', 'signature-agent'])
        self.assertEqual(params['created'], 1)
        self.assertEqual(params['expires'], 2)
        self.assertEqual(params['keyid'], 'k')
        self.assertEqual(params['tag'], 'web-bot-auth')
        self.assertTrue(raw.startswith('("@authority"'))

    def test_agent_origin_must_be_a_public_https_host(self):
        for bad in (
            '"http://agent.test"',
            '"https://web"',
            '"https://localhost"',
            '"https://10.0.0.5"',
            '"https://agent.test/path"',
            'https://agent.test',
            '',
        ):
            with self.subTest(bad=bad):
                self.assertIsNone(web_bot_auth.agent_origin(bad))
        self.assertEqual(web_bot_auth.agent_origin('"https://Agent.Test"'), 'https://agent.test')
        self.assertEqual(
            web_bot_auth.agent_origin('"https://agent.test:8443"'), 'https://agent.test:8443'
        )


@override_settings(TRUSTED_AGENT_PROXY_SECRET='')
class VerifyTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.signer = _Signer()
        patcher = mock.patch.object(web_bot_auth, '_fetch_jwks', return_value=self.signer.jwks())
        self.fetch = patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_valid_signature_attaches_the_agent(self):
        request = _run(self.signer.headers())
        agent = request.trusted_agent
        self.assertIsNotNone(agent)
        self.assertEqual(agent.provider, 'web-bot-auth')
        self.assertEqual(agent.agent_id, AGENT)
        self.assertEqual(agent.signature, self.signer.keyid)
        self.fetch.assert_called_once_with(AGENT)

    def test_the_directory_is_cached(self):
        _run(self.signer.headers())
        _run(self.signer.headers())
        self.assertEqual(self.fetch.call_count, 1)

    def test_a_key_without_kid_matches_by_thumbprint(self):
        self.fetch.return_value = self.signer.jwks(kid=False)
        self.assertIsNotNone(_run(self.signer.headers()).trusted_agent)

    def test_a_signature_for_another_host_is_ignored(self):
        self.assertIsNone(_run(self.signer.headers(authority='other.test')).trusted_agent)

    def test_expired_and_future_signatures_are_ignored(self):
        now = int(time.time())
        self.assertIsNone(
            _run(self.signer.headers(created=now - 700, expires=now - 100)).trusted_agent
        )
        self.assertIsNone(
            _run(self.signer.headers(created=now + 600, expires=now + 900)).trusted_agent
        )

    def test_a_window_longer_than_a_day_is_ignored(self):
        now = int(time.time())
        self.assertIsNone(_run(self.signer.headers(created=now, expires=now + 90000)).trusted_agent)

    def test_the_wrong_tag_is_ignored(self):
        self.assertIsNone(_run(self.signer.headers(tag='other')).trusted_agent)

    def test_authority_must_be_covered(self):
        self.assertIsNone(_run(self.signer.headers(components=('signature-agent',))).trusted_agent)

    def test_an_unknown_key_is_ignored(self):
        self.assertIsNone(_run(self.signer.headers(keyid='nope')).trusted_agent)

    def test_a_directory_that_cannot_be_fetched_fails_soft(self):
        self.fetch.side_effect = RuntimeError('boom')
        request = RequestFactory().get('/mcp/storefront/v1/', **self.signer.headers())
        response = TrustedAgentMiddleware(lambda r: HttpResponse('ok'))(request)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(request.trusted_agent)

    def test_a_failed_fetch_is_not_retried_on_every_request(self):
        self.fetch.side_effect = RuntimeError('boom')
        _run(self.signer.headers())
        _run(self.signer.headers())
        self.assertEqual(self.fetch.call_count, 1)

    def test_a_non_public_agent_origin_is_never_fetched(self):
        _run(self.signer.headers(agent='https://web'))
        _run(self.signer.headers(agent='http://agent.test'))
        self.fetch.assert_not_called()

    def test_a_garbled_header_is_ignored(self):
        headers = self.signer.headers()
        headers['HTTP_SIGNATURE_INPUT'] = 'sig1=(@authority;created=x'
        self.assertIsNone(_run(headers).trusted_agent)
        headers = self.signer.headers()
        headers['HTTP_SIGNATURE'] = 'sig1=:not base64!:'
        self.assertIsNone(_run(headers).trusted_agent)

    def test_requests_without_the_headers_are_untouched(self):
        request = _run({})
        self.assertIsNone(request.trusted_agent)
        self.fetch.assert_not_called()

    def test_the_agent_stamps_an_order(self):
        from plugins.installed.agent_mcp.middleware import stamp_order_with_agent
        from plugins.installed.orders.models import Order

        request = _run(self.signer.headers())
        from decimal import Decimal

        from djmoney.money import Money

        order = Order.objects.create(
            email='a@x.test',
            subtotal=Money(Decimal('8.00'), 'USD'),
            total=Money(Decimal('8.00'), 'USD'),
        )
        self.assertTrue(stamp_order_with_agent(order, request.trusted_agent))
        order = Order.objects.get(pk=order.pk)  # status is a protected FSM field
        self.assertEqual(order.metadata['agent_id'], AGENT)
        self.assertEqual(order.metadata['agent_provider'], 'web-bot-auth')


@override_settings(TRUSTED_AGENT_PROXY_SECRET='')
class ManifestTests(TestCase):
    def test_agent_json_advertises_origin_verification(self):
        from django.test import Client

        data = json.loads(Client().get('/.well-known/agent.json').content)
        self.assertTrue(data['accepts']['web_bot_auth'])
        self.assertFalse(data['accepts']['cloudflare_web_bot_auth'])
        self.assertEqual(data['web_bot_auth']['tag'], 'web-bot-auth')
        self.assertIn('Signature-Agent', data['web_bot_auth']['headers'])
        self.assertIn('@authority', data['web_bot_auth']['covered_components'])


class DirectoryFetchTests(SimpleTestCase):
    def test_fetch_uses_the_fixed_directory_path(self):
        with mock.patch('requests.get') as get:
            get.return_value = mock.Mock(
                status_code=200,
                headers={'Content-Length': '12'},
                iter_content=lambda chunk_size: iter([b'{"keys": []}']),
            )
            self.assertEqual(web_bot_auth._fetch_jwks('https://agent.test'), {'keys': []})
        url = get.call_args.args[0]
        self.assertEqual(url, 'https://agent.test/.well-known/http-message-signatures-directory')
        self.assertLessEqual(get.call_args.kwargs['timeout'], 5)
