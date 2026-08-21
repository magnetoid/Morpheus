"""MCP scope vocabulary + fail-closed semantics.

Three regressions locked here:

  * Every scope any registered tool declares MUST exist in AVAILABLE_SCOPES —
    a missing one cannot be granted in the dashboard (the form only renders
    catalog scopes), so a merchant could not scope a token to it and fell back
    to the wildcard. The whole scope system was decorative for ~22 scopes,
    incl. system.write (plugins.enable/disable). (F3)

  * token_scopes() fails CLOSED on a malformed value: a present-but-garbage
    `mcp_scopes` (a bare string, an int, null) denies rather than reading as
    the wildcard. Only a truly ABSENT key inherits wildcard (back-compat for
    unconfigured dict tokens + legacy raw-string tokens). (F5)

  * The token dashboard preserves scopes/approved_tools across a save — it used
    to drop them, and because a missing mcp_scopes reads as wildcard, any
    create/revoke silently promoted every other token to full access. (F1)
"""

from __future__ import annotations

from django.test import TestCase

from core.agents.registry import agent_registry
from plugins.installed.agent_mcp.scopes import (
    AVAILABLE_SCOPES,
    WILDCARD,
    token_scopes,
)


class ScopeVocabularyTests(TestCase):
    def test_every_tool_scope_is_in_the_catalog(self):
        catalog = set(AVAILABLE_SCOPES)
        used: dict[str, str] = {}
        for tool in agent_registry.platform_tools():
            for scope in getattr(tool, 'scopes', None) or []:
                used.setdefault(scope, tool.name)
        missing = {s: used[s] for s in used if s not in catalog}
        self.assertEqual(
            missing,
            {},
            'tool scopes missing from AVAILABLE_SCOPES (unselectable in the '
            f'dashboard → token falls back to wildcard): {sorted(missing)}',
        )


class TokenScopesFailClosedTests(TestCase):
    def test_absent_key_inherits_wildcard(self):
        # An unconfigured dict token (never had scopes set) keeps back-compat.
        self.assertEqual(token_scopes({'token': 't'}, 'mcp'), {WILDCARD})

    def test_legacy_raw_string_is_wildcard(self):
        self.assertEqual(token_scopes('raw-token', 'mcp'), {WILDCARD})

    def test_explicit_list_is_exact(self):
        self.assertEqual(
            token_scopes({'mcp_scopes': ['catalog.read', 'orders.read']}, 'mcp'),
            {'catalog.read', 'orders.read'},
        )

    def test_empty_list_is_no_scopes(self):
        self.assertEqual(token_scopes({'mcp_scopes': []}, 'mcp'), set())

    def test_malformed_values_fail_closed(self):
        # Present but garbage → DENY, never wildcard.
        for bad in ('catalog.read', 42, {'x': 1}, True):
            self.assertEqual(
                token_scopes({'mcp_scopes': bad}, 'mcp'),
                set(),
                f'malformed mcp_scopes={bad!r} must deny, not inherit wildcard',
            )

    def test_null_value_fails_closed(self):
        self.assertEqual(token_scopes({'mcp_scopes': None}, 'mcp'), set())


class DashboardEntryPreservationTests(TestCase):
    """Creating/revoking a token must not wipe other tokens' scopes."""

    def _seed(self):
        from plugins.models import PluginConfig

        PluginConfig.objects.update_or_create(
            plugin_name='agent_mcp',
            defaults={
                'config': {
                    'public_keys': [
                        {
                            'id': 'a',
                            'label': 'scoped',
                            'token': 'tok-a',
                            'mcp_scopes': ['catalog.read'],
                            'graphql_scopes': ['catalog.read'],
                            'approved_tools': ['orders.refund'],
                            'rate_limit_per_minute': 30,
                        }
                    ]
                }
            },
        )

    def test_create_preserves_existing_token_scopes(self):
        from plugins.installed.agent_mcp.dashboard import _load_entries, _save_entries

        self._seed()
        # Simulate the create action's round-trip.
        entries = _load_entries()
        entries.append({'id': 'b', 'label': 'new', 'token': 'tok-b'})
        _save_entries(entries)

        reloaded = {e['id']: e for e in _load_entries()}
        self.assertEqual(reloaded['a'].get('mcp_scopes'), ['catalog.read'])
        self.assertEqual(reloaded['a'].get('approved_tools'), ['orders.refund'])
        self.assertEqual(reloaded['a'].get('rate_limit_per_minute'), 30)
        # And the new token, having no mcp_scopes, is the wildcard-inheriting
        # unconfigured case — NOT a silent downgrade of token 'a'.
        self.assertNotIn('mcp_scopes', reloaded['b'])


class ScopeSemanticsTests(TestCase):
    """A tool declaring two scopes means BOTH (v0.58.0).

    The MCP edge used to pass on ONE match, so a token holding just
    `system.write` could call the self-coding tools
    (scopes=['system.write','selfdev']) without `selfdev` — the ADR 0014
    "selfdev is Linda-only" gate, bypassed. Now aligned with the in-process
    runtime (policies.enforce_policy) and Tool's own docstring.
    """

    def test_all_required_scopes_must_be_held(self):
        from plugins.installed.agent_mcp.scopes import has_scopes

        self.assertTrue(has_scopes({'system.write', 'selfdev'}, ['system.write', 'selfdev']))
        self.assertFalse(
            has_scopes({'system.write'}, ['system.write', 'selfdev']),
            'a partial match must NOT satisfy a multi-scope tool (selfdev bypass)',
        )
        self.assertFalse(has_scopes({'selfdev'}, ['system.write', 'selfdev']))

    def test_single_scope_behaviour_is_unchanged(self):
        from plugins.installed.agent_mcp.scopes import has_scopes

        self.assertTrue(has_scopes({'catalog.read'}, ['catalog.read']))
        self.assertFalse(has_scopes({'orders.read'}, ['catalog.read']))

    def test_wildcard_and_public_ops_still_pass(self):
        from plugins.installed.agent_mcp.scopes import has_scopes

        self.assertTrue(has_scopes({'*'}, ['system.write', 'selfdev']))
        self.assertTrue(has_scopes(set(), []))  # no declared scopes = public op

    def test_legacy_alias_shares_the_new_semantics(self):
        from plugins.installed.agent_mcp.scopes import has_any

        self.assertFalse(has_any({'system.write'}, ['system.write', 'selfdev']))
