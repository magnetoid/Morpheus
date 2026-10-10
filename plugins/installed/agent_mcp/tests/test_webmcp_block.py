"""The storefront registers WebMCP tools, and every tool's query is real.

Chrome 149 ships WebMCP in an origin trial and Lighthouse's "Agentic Browsing"
category scores a page on the tools it registers and the validity of their
schemas; on 2026-10-10 every store scored "not applicable" because nothing was
registered. The block is contributed by ``agent_mcp`` (the agent gateway), so
it vanishes when that app is off, and the tool definitions live in Python so
their GraphQL can be validated here rather than discovered broken in a browser.
"""

from __future__ import annotations

import re

from django.template.loader import get_template
from django.test import TestCase
from graphql import parse, validate

from plugins.installed.agent_mcp.webmcp import TOOLS


class WebMcpBlockTests(TestCase):
    def test_the_block_renders_on_the_storefront(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'morph-webmcp-tools')
        self.assertContains(r, 'registerTool')
        for tool in TOOLS:
            self.assertContains(r, tool['name'])

    def test_the_template_compiles(self):
        get_template('agent_mcp/blocks/webmcp.html')

    def test_the_block_vanishes_when_the_gateway_is_off(self):
        from plugins.registry import app_registry

        app_registry.deactivate('agent_mcp')
        self.addCleanup(app_registry.activate, 'agent_mcp')
        r = self.client.get('/')
        self.assertNotContains(r, 'morph-webmcp-tools')


class WebMcpToolDefinitionTests(TestCase):
    def test_every_query_is_valid_for_the_schema(self):
        from api.schema import get_schema

        schema = get_schema()._schema
        for tool in TOOLS:
            with self.subTest(tool=tool['name']):
                self.assertEqual(validate(schema, parse(tool['graphql'])), [])

    def test_schemas_are_json_schema_objects(self):
        names = [t['name'] for t in TOOLS]
        self.assertEqual(len(names), len(set(names)))
        for tool in TOOLS:
            with self.subTest(tool=tool['name']):
                self.assertRegex(tool['name'], r'^[a-z_]+$')
                self.assertTrue(tool['description'])
                schema = tool['inputSchema']
                self.assertEqual(schema['type'], 'object')
                self.assertIsInstance(schema['properties'], dict)
                for required in schema.get('required', []):
                    self.assertIn(required, schema['properties'])

    def test_variables_only_reference_declared_inputs(self):
        def refs(spec):
            if isinstance(spec, str):
                return [spec[1:]] if spec.startswith('$') else []
            if isinstance(spec, dict):
                return [r for v in spec.values() for r in refs(v)]
            return []

        for tool in TOOLS:
            with self.subTest(tool=tool['name']):
                declared = set(tool['inputSchema']['properties'])
                for name in refs(tool['variables']):
                    self.assertIn(name, declared)
                # Every GraphQL variable the query declares is supplied.
                for var in re.findall(r'\$(\w+)\s*:', tool['graphql']):
                    self.assertIn(var, tool['variables'])
