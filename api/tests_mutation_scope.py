"""One scope check for every staff GraphQL mutation, and API keys pass it.

catalog, inventory, orders and book_product each had their own `_check_scope`.
Catalog's was fixed in v0.83.5 to judge every token through `has_scope`; the
other three kept the old shape — staff-only, then a direct read of
`_morph_token_scopes_graphql` — so a core API key holding `inventory.write`
or `orders.write` was refused (`graphql_view` leaves the empty deny-first set
behind for any Bearer token that is not an MCP token). Two copies of one rule
drift; there is now one, `api.graphql_permissions.mutation_scope_error`.
"""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from api.graphql_permissions import mutation_scope_error


class _Info:
    def __init__(self, request):
        self.context = {'request': request}


def _info(*, user=None, token=None, agent=None):
    req = RequestFactory().post('/graphql/')
    req.user = user or AnonymousUser()
    if token is not None:
        req._morph_token_scopes_graphql = set(token)
    if agent is not None:
        req.agent_capabilities = {'scopes': list(agent), 'is_agent': True}
    return _Info(req)


class MutationScopeTests(TestCase):
    def _user(self, staff):
        return get_user_model().objects.create_user(
            username=f'scope-{staff}', email=f'scope-{staff}@x.io', password='pw', is_staff=staff
        )

    def test_the_matrix(self):
        staff, customer = self._user(True), self._user(False)
        allowed = [
            _info(user=staff),
            _info(user=staff, token={'orders.write'}),
            _info(user=staff, token={'*'}),
            _info(token=set(), agent=['orders.write']),
            _info(token=set(), agent=['admin']),
        ]
        refused = [
            _info(),
            _info(user=customer),
            _info(user=staff, token={'catalog.read'}),
            _info(user=staff, token=set()),
            _info(token=set(), agent=['catalog.write']),
        ]
        for info in allowed:
            self.assertEqual(mutation_scope_error(info, ['orders.write']), '')
        for info in refused:
            self.assertTrue(mutation_scope_error(info, ['orders.write']))

    def test_every_app_uses_the_one_check(self):
        from plugins.installed.book_product.graphql import _auth as book_auth
        from plugins.installed.catalog.graphql import mutations as catalog
        from plugins.installed.inventory.graphql import mutations as inventory
        from plugins.installed.orders.graphql import mutations as orders

        self.assertIs(catalog._check_scope, mutation_scope_error)
        self.assertIs(inventory._check_scope, mutation_scope_error)
        self.assertIs(orders._check_scope, mutation_scope_error)
        self.assertIs(book_auth.check_scope, mutation_scope_error)


class ApiKeyMutationTests(TestCase):
    """Through the real middleware and view: the right key gets past auth to the
    mutation's own answer ("not found"); the wrong one is refused for its scope."""

    def _post(self, scopes, query):
        from core.models import APIKey

        key = APIKey.objects.create(name='K', scopes=scopes)._raw_key
        resp = self.client.post(
            '/graphql/agent/',
            data=json.dumps({'query': query}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {key}',
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()['data']

    def test_inventory_orders_and_books_accept_a_scoped_key(self):
        cases = [
            (
                'inventory.write',
                'mutation { setStock(input: {variantSku: "nope", quantity: 3}) { error } }',
                'setStock',
                'variant not found',
            ),
            (
                'orders.write',
                'mutation { markOrderFulfilled(input: {orderNumber: "NOPE-1"}) { error } }',
                'markOrderFulfilled',
                'not found',
            ),
            (
                'catalog.write',
                'mutation { setBookProduct(input: {productSlug: "nope"}) { ok error } }',
                'setBookProduct',
                'No product',
            ),
        ]
        for scope, query, field, past_auth in cases:
            with self.subTest(scope=scope):
                self.assertIn(past_auth, self._post([scope], query)[field]['error'])
                refused = self._post(['cms.write'], query)[field]['error']
                self.assertIn('token missing scope', refused)
