"""CSRF applies to a staff session; only a Bearer token is exempt.

Four JSON endpoints were ``@csrf_exempt`` because API clients call them with a
Bearer token — and they also accepted a plain staff session. A page on another
site could therefore POST to them with the merchant's cookies, protected only by
the browser's SameSite default. The exemption now holds only when the request
carries ``Authorization: Bearer``; a session request goes through Django's
normal CSRF check.
"""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase


class _Base(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='csrf-staff', email='csrf@x.test', password='pw', is_staff=True
        )
        self.c = Client(enforce_csrf_checks=True)
        self.c.force_login(self.staff)

    def _post(self, path, **extra):
        return self.c.post(
            path,
            data=json.dumps({'message': 'hi', 'prompt': 'hi'}),
            content_type='application/json',
            **extra,
        )


class LlmTasksCsrfTests(_Base):
    def test_a_session_post_without_the_token_is_refused(self):
        r = self._post('/api/llm-tasks/')
        self.assertEqual(r.status_code, 403)
        self.assertIn('CSRF', r.content.decode())

    def test_a_bearer_request_skips_csrf_and_reaches_the_view(self):
        # No session: the view's own auth answers 401 for the bogus token
        # instead of Django's CSRF page answering 403.
        anonymous = Client(enforce_csrf_checks=True)
        r = anonymous.post(
            '/api/llm-tasks/',
            data=json.dumps({'prompt': 'hi'}),
            content_type='application/json',
            HTTP_AUTHORIZATION='Bearer not-a-real-token',
        )
        self.assertEqual(r.status_code, 401)

    def test_a_session_get_is_not_affected(self):
        r = self.c.get('/api/llm-tasks/00000000-0000-0000-0000-000000000000/')
        self.assertEqual(r.status_code, 404)


class AgentInvokeCsrfTests(_Base):
    def test_a_session_post_without_the_token_is_refused(self):
        r = self._post('/api/agents/nope/invoke')
        self.assertEqual(r.status_code, 403)
        self.assertIn('CSRF', r.content.decode())

    def test_a_bearer_request_skips_csrf_and_reaches_the_view(self):
        r = self._post('/api/agents/nope/invoke', HTTP_AUTHORIZATION='Bearer not-a-real-token')
        self.assertEqual(r.status_code, 404)
        self.assertIn('Unknown agent', r.json()['error'])

    def test_stream_is_gated_the_same_way(self):
        r = self._post('/api/agents/nope/stream')
        self.assertEqual(r.status_code, 403)
        r = self._post('/api/agents/nope/stream', HTTP_AUTHORIZATION='Bearer not-a-real-token')
        self.assertEqual(r.status_code, 404)


class GraphqlBearerCsrfTests(TestCase):
    """An external agent POSTs to /graphql/ with a Bearer token and no cookies.

    The tokens page tells every merchant to do exactly that, but the main
    GraphQL route was not CSRF-exempt for Bearer requests, so Django's CSRF
    middleware answered 403 before the token was ever read.
    """

    def setUp(self):
        from plugins.models import PluginConfig

        self.token = 'mph_csrf-graphql-probe-token-1234567890'
        PluginConfig.objects.update_or_create(
            plugin_name='agent_mcp',
            defaults={
                'config': {
                    'public_keys': [
                        {'id': 'csrf-probe', 'label': 'csrf probe', 'token': self.token}
                    ]
                }
            },
        )

    def test_a_bearer_query_reaches_graphql_without_a_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        r = client.post(
            '/graphql/',
            data=json.dumps({'query': '{ __typename }'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(r.json()['data']['__typename'], 'Query')

    def test_a_session_post_without_the_token_is_still_refused(self):
        staff = get_user_model().objects.create_user(
            username='gql-staff', email='gql@x.test', password='pw', is_staff=True
        )
        client = Client(enforce_csrf_checks=True)
        client.force_login(staff)
        r = client.post(
            '/graphql/',
            data=json.dumps({'query': '{ __typename }'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 403)
