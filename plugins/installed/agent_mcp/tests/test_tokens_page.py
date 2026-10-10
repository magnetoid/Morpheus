"""The API tokens page: a token starts from a purpose, and hands over a connection.

Owner's asks (2026-10-10): "copy connection code" on a token, with everything the
other party needs; drop the JSON example cards. Found on the way: a new token was
an implicit wildcard, nobody was recorded as its creator, nothing was audited,
and the approval checklist was always empty, so every save wiped the grants.
"""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase

PAGE = '/dashboard/apps/agent_mcp/tokens/'


def _entries() -> list[dict]:
    from plugins.models import PluginConfig

    cfg = PluginConfig.objects.filter(plugin_name='agent_mcp').first()
    return list(((cfg.config if cfg else {}) or {}).get('public_keys') or [])


class TokensPageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.owner = get_user_model().objects.create_user(
            username='owner', email='owner@example.com', password='x', is_staff=True,
            is_superuser=True,
        )  # fmt: skip
        self.c = Client()
        self.c.force_login(self.owner)

    def _create(self, preset: str, label: str = 'Hermes on the laptop'):
        return self.c.post(PAGE, {'action': 'create', 'label': label, 'preset': preset})

    def test_a_janus_token_gets_the_grant_and_read_scopes_and_its_creator(self):
        from core.audit.models import AuditEvent

        response = self._create('janus_read')
        self.assertEqual(response.status_code, 200)
        (entry,) = _entries()
        for surface in ('mcp_scopes', 'graphql_scopes'):
            self.assertIn('janus.chat', entry[surface])
            self.assertIn('catalog.read', entry[surface])
            self.assertFalse(any(s.endswith('.write') for s in entry[surface]))
            self.assertNotIn('*', entry[surface])
        self.assertEqual(
            entry['created_by'], {'id': str(self.owner.pk), 'email': 'owner@example.com'}
        )
        self.assertTrue(AuditEvent.objects.filter(event_type='mcp.token_created').exists())

    def test_no_preset_is_an_implicit_wildcard(self):
        self._create('custom')
        (entry,) = _entries()
        self.assertEqual((entry['mcp_scopes'], entry['graphql_scopes']), ([], []))

    def test_full_access_includes_janus_explicitly(self):
        self._create('full')
        (entry,) = _entries()
        self.assertEqual(sorted(entry['mcp_scopes']), ['*', 'janus.chat'])

    def test_the_new_token_comes_with_its_connection_details(self):
        body = self._create('janus_read').content.decode()
        (entry,) = _entries()
        self.assertIn('data-connection-text', body)
        self.assertIn(f'Authorization: Bearer {entry["token"]}', body)
        self.assertIn('http://testserver/mcp/admin/v1/', body)
        self.assertIn('mcp_servers:', body)  # Hermes Agent
        self.assertIn('openclaw mcp set', body)
        self.assertIn('claude mcp add --transport http', body)
        self.assertIn('janus.ask', body)

    def test_an_existing_tokens_details_never_show_its_secret(self):
        self._create('janus_read')
        (entry,) = _entries()
        body = self.c.get(PAGE, {'connect': entry['id']}).content.decode()
        self.assertIn('data-connection-text', body)
        self.assertNotIn(entry['token'], body)
        self.assertIn('PASTE_YOUR_TOKEN_HERE', body)

    def test_a_new_secret_keeps_the_token_and_ends_the_old_one(self):
        from core.audit.models import AuditEvent
        from plugins.installed.agent_mcp.views import _api_keys

        self._create('janus_read')
        (before,) = _entries()
        body = self.c.post(PAGE, {'action': 'rotate', 'id': before['id']}).content.decode()
        (after,) = _entries()
        self.assertEqual(
            (after['id'], after['label'], after['mcp_scopes']),
            (before['id'], before['label'], before['mcp_scopes']),
        )
        self.assertNotEqual(after['token'], before['token'])
        self.assertNotIn(before['token'], _api_keys())
        self.assertIn(f'Authorization: Bearer {after["token"]}', body)
        self.assertTrue(AuditEvent.objects.filter(event_type='mcp.token_rotated').exists())

    def test_revoking_is_audited(self):
        from core.audit.models import AuditEvent

        self._create('read')
        (entry,) = _entries()
        self.c.post(PAGE, {'action': 'revoke', 'id': entry['id']})
        self.assertEqual(_entries(), [])
        self.assertTrue(AuditEvent.objects.filter(event_type='mcp.token_revoked').exists())

    def test_the_approval_list_names_protected_tools_and_a_save_keeps_the_rest(self):
        from plugins.installed.agent_mcp.dashboard import _approval_tool_names

        names = _approval_tool_names()
        self.assertTrue(names, 'protected tools a token can be granted')
        self._create('custom')
        (entry,) = _entries()
        from plugins.installed.agent_mcp.dashboard import _save_entries

        entry['approved_tools'] = ['hand.granted_tool', names[0]]
        _save_entries([entry])
        self.c.post(
            PAGE,
            {
                'action': 'save_scopes',
                'id': entry['id'],
                'mcp_wildcard': 'on',
                'mcp_janus.chat': 'on',
            },
        )
        (saved,) = _entries()
        self.assertEqual(sorted(saved['mcp_scopes']), ['*', 'janus.chat'])
        # A grant the form did not show survives; a shown, unticked one is removed.
        self.assertEqual(saved['approved_tools'], ['hand.granted_tool'])

    def test_the_example_cards_are_gone(self):
        body = self.c.get(PAGE).content.decode()
        self.assertNotIn('Common product-lifecycle mutations', body)
        self.assertNotIn('catalog.publish_digital_product', body)

    def test_the_connection_text_names_every_endpoint(self):
        from plugins.installed.agent_mcp.connection import connection_kit

        kit = connection_kit(
            base_url='https://shop.example',
            store_name='Supernatural Shop',
            entry={
                'id': 'x',
                'label': 'n8n',
                'mcp_scopes': ['janus.chat', 'catalog.read'],
                'graphql_scopes': ['janus.chat'],
            },
            secret='mph_secret',
        )
        self.assertIn('https://shop.example/mcp/admin/v1/', kit['text'])
        self.assertIn('https://shop.example/graphql/', kit['text'])
        self.assertIn('Authorization: Bearer mph_secret', kit['text'])
        ids = {s['id'] for s in kit['snippets']}
        self.assertTrue({'hermes', 'openclaw', 'claude-code', 'mcp-json', 'curl'} <= ids)
        hermes = next(s for s in kit['snippets'] if s['id'] == 'hermes')['code']
        self.assertIn('supernatural-shop:', hermes)
        cursor = json.loads(next(s for s in kit['snippets'] if s['id'] == 'mcp-json')['code'])
        self.assertEqual(
            cursor['mcpServers']['supernatural-shop']['url'], 'https://shop.example/mcp/admin/v1/'
        )
