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
