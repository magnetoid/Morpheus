"""Every staff GraphQL surface is judged by scope, never by ``is_staff`` alone.

An MCP token resolves to a shared ``is_staff`` service user, so a resolver that
asked ``is_staff(info)`` let any valid token through whatever its GraphQL
scopes: CRM leads and customer timelines (PII), agent runs and steps (full tool
arguments and outputs), and payment intents for any order. Each now asks
``has_scope`` for its own scope, which a core API key or an MCP token must
hold.
"""

from __future__ import annotations

import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money


class _Api(TestCase):
    def _post(self, scopes, query):
        from core.models import APIKey

        key = APIKey.objects.create(name='K', scopes=scopes)._raw_key
        resp = self.client.post(
            '/graphql/agent/',
            data=json.dumps({'query': query}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {key}',
        )
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        return resp.json()['data']


class CrmScopeTests(_Api):
    def test_leads_need_crm_read(self):
        from plugins.installed.crm.models import Lead

        Lead.objects.create(email='lead@example.com')
        q = '{ crmLeads { email } }'
        self.assertEqual(len(self._post(['crm.read'], q)['crmLeads']), 1)
        self.assertEqual(self._post(['catalog.read'], q)['crmLeads'], [])

    def test_create_lead_needs_crm_write(self):
        q = 'mutation { crmCreateLead(input: {email: "new@example.com"}) { email error } }'
        refused = self._post(['crm.read'], q)['crmCreateLead']
        self.assertIn('token missing scope', refused['error'])
        allowed = self._post(['crm.write'], q)['crmCreateLead']
        self.assertEqual(allowed['error'], '')


class AgentRunScopeTests(_Api):
    def test_runs_and_steps_need_agents_read(self):
        from core.agents.models import AgentRun

        run = AgentRun.objects.create(agent_name='worker', user_message='hi', state='completed')
        q = '{ agentRuns { id } }'
        self.assertEqual(len(self._post(['agents.read'], q)['agentRuns']), 1)
        self.assertEqual(self._post(['crm.read'], q)['agentRuns'], [])
        steps = f'{{ agentRunSteps(runId: "{run.id}") {{ seq }} }}'
        self.assertEqual(self._post(['crm.read'], steps)['agentRunSteps'], [])


class PaymentIntentScopeTests(_Api):
    def test_staff_intent_for_someone_elses_order_needs_orders_write(self):
        from plugins.installed.orders.models import Order

        order = Order.objects.create(
            email='buyer@example.com', subtotal=Money(10, 'USD'), total=Money(10, 'USD')
        )
        q = f'mutation {{ createPaymentIntent(orderId: "{order.id}") {{ success error }} }}'
        self.assertEqual(
            self._post(['crm.read'], q)['createPaymentIntent']['error'], 'Order not found'
        )
        allowed = self._post(['orders.write'], q)['createPaymentIntent']
        self.assertNotEqual(allowed['error'], 'Order not found')


class SessionStaffRbacTests(TestCase):
    """A dashboard session is judged by the RBAC seam, not by ``is_staff`` alone,
    so a role that lost a capability loses the GraphQL write once ``rbac``
    enforces (the seam is mode-aware and changes nothing in log mode)."""

    def test_mutation_scope_error_consults_the_capability_check(self):
        from django.test import RequestFactory

        from api.graphql_permissions import mutation_scope_error

        staff = get_user_model().objects.create_user(
            username='rbac-staff', email='rbac@x.test', password='pw', is_staff=True
        )
        req = RequestFactory().post('/graphql/')
        req.user = staff

        class _Info:
            context = {'request': req}

        with mock.patch('core.authz.check', return_value=False) as check:
            self.assertTrue(mutation_scope_error(_Info(), ['orders.write']))
        check.assert_called_once()
        self.assertEqual(check.call_args.args[1], 'orders.write')


class EmptyScopeProjectionTests(TestCase):
    def test_an_explicitly_empty_graphql_scope_list_is_not_a_wildcard(self):
        from django.test import RequestFactory

        from api.permissions import AgentAuthMiddleware

        req = RequestFactory().post('/graphql/agent/', HTTP_AUTHORIZATION='Bearer tok')

        def _apply(request):
            request._morph_token_scopes_graphql = set()
            return True

        with mock.patch('plugins.installed.agent_mcp.auth.apply_bearer_user', _apply):
            AgentAuthMiddleware(lambda r: None)(req)
        self.assertEqual(req.agent_capabilities['scopes'], [])
