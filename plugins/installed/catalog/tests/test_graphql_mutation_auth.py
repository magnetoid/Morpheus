"""Who may run the catalog GraphQL mutations.

Four kinds of caller reach ``_check_scope``:

* a dashboard session (staff, no token): allowed, as before;
* an MCP token from the dashboard: a staff service user, confined to the
  token's own GraphQL scopes;
* a core ``APIKey`` on ``/graphql/agent/``: no user at all, confined to the
  key's scopes. ``graphql_view`` also runs ``apply_bearer_user`` for it, which
  stashes the empty deny-first scope set, so a check that reads that set
  directly denied every such key (v0.83.5);
* anyone else: refused.
"""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from plugins.installed.catalog.graphql.mutations import _check_scope


class _Info:
    def __init__(self, request):
        self.context = {'request': request}


def _request(*, user=None, token_scopes=None, agent_scopes=None):
    req = RequestFactory().post('/graphql/agent/')
    req.user = user or AnonymousUser()
    if token_scopes is not None:
        req._morph_token_scopes_graphql = set(token_scopes)
    if agent_scopes is not None:
        req.agent_capabilities = {'scopes': list(agent_scopes), 'is_agent': True}
    return _Info(req)


class CheckScopeTests(TestCase):
    def _user(self, *, staff):
        return get_user_model().objects.create_user(
            username=f'catalog-auth-{staff}', email='a@example.test', password='pw', is_staff=staff
        )

    def test_anonymous_is_refused(self):
        self.assertTrue(_check_scope(_request(), ['catalog.write']))

    def test_signed_in_customer_is_refused(self):
        self.assertTrue(_check_scope(_request(user=self._user(staff=False)), ['catalog.write']))

    def test_dashboard_staff_session_is_allowed(self):
        self.assertEqual(
            _check_scope(_request(user=self._user(staff=True)), ['catalog.delete']), ''
        )

    def test_mcp_token_is_confined_to_its_scopes(self):
        staff = self._user(staff=True)
        self.assertEqual(
            _check_scope(_request(user=staff, token_scopes={'catalog.write'}), ['catalog.write']),
            '',
        )
        self.assertTrue(
            _check_scope(_request(user=staff, token_scopes={'catalog.read'}), ['catalog.write'])
        )
        self.assertTrue(_check_scope(_request(user=staff, token_scopes=set()), ['catalog.write']))

    def test_api_key_with_the_scope_is_allowed_despite_the_empty_token_stash(self):
        info = _request(token_scopes=set(), agent_scopes=['catalog.write'])
        self.assertEqual(_check_scope(info, ['catalog.write']), '')

    def test_api_key_is_confined_to_its_scopes(self):
        writer = _request(token_scopes=set(), agent_scopes=['catalog.write'])
        self.assertTrue(_check_scope(writer, ['catalog.delete']))
        other = _request(token_scopes=set(), agent_scopes=['cms.write', 'catalog.read'])
        self.assertTrue(_check_scope(other, ['catalog.write']))

    def test_api_key_admin_scope_covers_catalog(self):
        # APIKey.has_scope's own rule: 'admin' holds every scope.
        info = _request(token_scopes=set(), agent_scopes=['admin'])
        self.assertEqual(_check_scope(info, ['catalog.delete']), '')


class AgentEndpointTests(TestCase):
    """The same rules through the real middleware and GraphQL view."""

    def _key(self, scopes):
        from core.models import APIKey, StoreChannel

        channel = StoreChannel.objects.create(name='Agent', domain=f'agent-{len(scopes)}.test')
        return APIKey.objects.create(name='Agent', scopes=scopes, channel=channel)._raw_key

    def _post(self, key, query):
        resp = self.client.post(
            '/graphql/agent/',
            data=json.dumps({'query': query}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {key}',
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()['data']

    def test_key_without_catalog_write_cannot_create_a_category(self):
        from plugins.installed.catalog.models import Category

        data = self._post(
            self._key(['cms.write', 'catalog.read']),
            'mutation { createCategory(input: {name: "No", slug: "no"}) { slug error } }',
        )
        self.assertTrue(data['createCategory']['error'])
        self.assertFalse(Category.objects.filter(slug='no').exists())

    def test_catalog_write_key_cannot_archive_a_category(self):
        from plugins.installed.catalog.models import Category

        Category.objects.create(name='Keep', slug='keep')
        data = self._post(
            self._key(['catalog.write']),
            'mutation { archiveCategory(slug: "keep") { slug error } }',
        )
        self.assertTrue(data['archiveCategory']['error'])
        self.assertTrue(Category.objects.filter(slug='keep').exists())
