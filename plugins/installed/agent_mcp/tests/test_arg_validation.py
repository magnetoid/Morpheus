"""MCP tool-argument validation + discovery rate limiting (v0.57.0).

Tool.invoke silently drops args the handler doesn't name, so before this an
out-of-range or wrong-typed argument reached the handler (and the ORM) as a
default-valued "success". And the discovery methods (initialize/tools/list/
resources/list/ping) ran a DB query with no rate limit — free tool-inventory
enumeration + a cheap DB-amplification vector.
"""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase

from core.agents.tools import Tool
from plugins.installed.agent_mcp import views


def _tool(schema):
    return Tool(name='t.x', description='x', handler=lambda **kw: None, schema=schema)


class ArgValidationTests(TestCase):
    SCHEMA = {
        'type': 'object',
        'properties': {
            'days': {'type': 'integer', 'minimum': 1, 'maximum': 365},
            'mode': {'type': 'string', 'enum': ['a', 'b']},
            'note': {'type': 'string', 'maxLength': 5},
        },
        'required': ['days'],
    }

    def test_valid_args_pass(self):
        self.assertEqual(
            views._validate_tool_args(_tool(self.SCHEMA), {'days': 7, 'mode': 'a'}), ''
        )

    def test_missing_required(self):
        self.assertIn('required', views._validate_tool_args(_tool(self.SCHEMA), {'mode': 'a'}))

    def test_wrong_type(self):
        self.assertIn(
            'must be integer', views._validate_tool_args(_tool(self.SCHEMA), {'days': 'x'})
        )

    def test_bool_is_not_an_integer(self):
        # bool subclasses int — must be rejected for an integer field.
        self.assertIn(
            'must be integer', views._validate_tool_args(_tool(self.SCHEMA), {'days': True})
        )

    def test_out_of_range(self):
        self.assertIn('<= 365', views._validate_tool_args(_tool(self.SCHEMA), {'days': 999}))
        self.assertIn('>= 1', views._validate_tool_args(_tool(self.SCHEMA), {'days': 0}))

    def test_enum(self):
        self.assertIn(
            'one of', views._validate_tool_args(_tool(self.SCHEMA), {'days': 1, 'mode': 'z'})
        )

    def test_maxlength(self):
        self.assertIn(
            'too long',
            views._validate_tool_args(_tool(self.SCHEMA), {'days': 1, 'note': 'toolong'}),
        )

    def test_no_schema_is_permissive(self):
        self.assertEqual(views._validate_tool_args(_tool(None), {'whatever': 1}), '')

    def test_undeclared_arg_is_allowed(self):
        # Under-specified schemas are common — an extra arg must not be rejected.
        self.assertEqual(views._validate_tool_args(_tool(self.SCHEMA), {'days': 1, 'extra': 9}), '')


class DiscoveryRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        views._request_state.rl_client = 'ip:test-1.2.3.4'

    def tearDown(self):
        views._request_state.rl_client = ''

    def test_discovery_is_capped(self):
        limit = views._MCP_DISCOVERY_RATE_PER_MINUTE
        # Up to the limit: no raise.
        for _ in range(limit):
            views._enforce_discovery_rate_limit('tools/list')
        # The next call trips it.
        with self.assertRaises(views._RpcError) as ctx:
            views._enforce_discovery_rate_limit('tools/list')
        self.assertEqual(ctx.exception.code, views._E_RATE)
