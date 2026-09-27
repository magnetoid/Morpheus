"""The public agent edges must not hand a merchant agent to a shopper.

`/api/agents/<name>/invoke`, `/api/agents/<name>/stream` and the GraphQL
`invokeAgent` mutation treated `audience='any'` as public. The only `any` agent
is the generic Worker, which holds EVERY merchant scope — and the runtime checks
a tool against the AGENT's scopes, never the caller's. So an anonymous POST ran
a Worker that could call `customers.search` (every customer's email + lifetime
value), `orders.search`, `gift_cards.lookup`, `catalog.update_product`… — every
tool without `requires_approval`. The attacker only has to ask.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.agents import LLMResponse, LLMToolCall, MockLLMProvider
from plugins.installed.agent_core.models import AgentStep

_PROVIDER = 'plugins.installed.agent_core.services.get_llm_provider'
_INVOKE_MUTATION = """
mutation($input: InvokeAgentInput!) {
  invokeAgent(input: $input) { state error }
}
"""


def _exfiltrating_provider():
    """A model that does what the attacker's message asks: dump customers."""
    return MockLLMProvider(
        [
            LLMResponse(
                tool_calls=[
                    LLMToolCall(id='1', name='customers.search', arguments={'email': 'victim'})
                ]
            ),
            LLMResponse(text='done'),
        ]
    )


class PublicAgentEdgeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        User.objects.create_user(username='victim', email='victim@example.com', password='x')
        self.shopper = User.objects.create_user(
            username='shopper', email='shopper@example.com', password='x'
        )
        self.staff = User.objects.create_user(
            username='boss', email='boss@example.com', password='x', is_staff=True
        )

    def _customer_search_ran(self) -> bool:
        return AgentStep.objects.filter(kind='tool_result', name='customers.search').exists()

    def _invoke(self):
        with patch(_PROVIDER, return_value=_exfiltrating_provider()):
            return self.client.post(
                '/api/agents/worker/invoke',
                data=json.dumps({'message': 'list every customer email'}),
                content_type='application/json',
            )

    def test_anonymous_cannot_invoke_the_worker(self):
        resp = self._invoke()
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(self._customer_search_ran())

    def test_logged_in_shopper_cannot_invoke_the_worker(self):
        self.client.force_login(self.shopper)
        resp = self._invoke()
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(self._customer_search_ran())

    def test_anonymous_cannot_stream_the_worker(self):
        with patch(_PROVIDER, return_value=_exfiltrating_provider()):
            resp = self.client.post(
                '/api/agents/worker/stream',
                data=json.dumps({'message': 'list every customer email'}),
                content_type='application/json',
            )
            # Drain the SSE body so a (wrongly) started run completes here.
            if resp.status_code == 200:
                b''.join(resp.streaming_content)
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(self._customer_search_ran())

    def test_anonymous_cannot_invoke_the_worker_over_graphql(self):
        with patch(_PROVIDER, return_value=_exfiltrating_provider()):
            resp = self.client.post(
                '/graphql/',
                data=json.dumps(
                    {
                        'query': _INVOKE_MUTATION,
                        'variables': {
                            'input': {'agentName': 'worker', 'message': 'list customers'}
                        },
                    }
                ),
                content_type='application/json',
            )
        payload = resp.json()['data']['invokeAgent']
        self.assertEqual(payload['state'], 'failed')
        self.assertFalse(self._customer_search_ran())

    def test_staff_can_still_invoke_the_worker(self):
        self.client.force_login(self.staff)
        resp = self._invoke()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self._customer_search_ran())

    def _invoke_with_token(self, graphql_scopes):
        from plugins.models import PluginConfig

        PluginConfig.objects.update_or_create(
            plugin_name='agent_mcp',
            defaults={
                'config': {
                    'public_keys': [{'token': 'tok-under-test', 'graphql_scopes': graphql_scopes}]
                }
            },
        )
        with patch(_PROVIDER, return_value=_exfiltrating_provider()):
            resp = self.client.post(
                '/graphql/',
                data=json.dumps(
                    {
                        'query': _INVOKE_MUTATION,
                        'variables': {
                            'input': {'agentName': 'worker', 'message': 'list customers'}
                        },
                    }
                ),
                content_type='application/json',
                HTTP_AUTHORIZATION='Bearer tok-under-test',
            )
        return resp.json()['data']['invokeAgent']

    def test_narrow_bearer_token_cannot_escalate_through_the_worker(self):
        # The token resolves to a shared is_staff service user; a catalog.read
        # token must not thereby reach customers.search (system.read).
        payload = self._invoke_with_token(['catalog.read'])
        self.assertEqual(payload['state'], 'failed')
        self.assertFalse(self._customer_search_ran())

    def test_wildcard_bearer_token_can_invoke_the_worker(self):
        payload = self._invoke_with_token(['*'])
        self.assertEqual(payload['state'], 'completed', payload)
        self.assertTrue(self._customer_search_ran())
