"""
Morpheus CMS — Schema Introspector
Single source of truth for walking the Strawberry GraphQL schema.
Eliminates the DRY violation where manifest.py, mcp_server.py, and operator.py
all independently duplicated this logic.
"""

from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger('morpheus.api.introspector')

# Fields to always skip — system internals not useful to external agents
_SKIP_QUERY_FIELDS = frozenset(['ping', 'version', 'active_plugins'])

_GQL_TO_JSON_TYPE = {
    'String': 'string',
    'ID': 'string',
    'Int': 'integer',
    'Float': 'number',
    'Boolean': 'boolean',
}


def _gql_type_to_json(gql_type) -> str:
    """Walk a possibly-wrapped type (NonNull, List) to find the leaf scalar name."""
    # Unwrap NonNull / List wrappers
    inner = gql_type
    for attr in ('of_type', 'type'):
        while getattr(inner, attr, None) is not None:
            inner = getattr(inner, attr)
    name = getattr(inner, 'name', '') or ''
    return _GQL_TO_JSON_TYPE.get(name, 'string')


def _is_required(arg_type) -> bool:
    """A GraphQL argument is required when the outermost wrapper is NonNull."""
    # Strawberry marks optionality via is_optional on the annotation, but
    # the safe fallback is to check if the type is explicitly Optional.
    return not getattr(arg_type, 'is_optional', True)


def build_field_schema(field) -> dict:
    """
    Build a JSON Schema 'object' describing the arguments of a single GraphQL field.
    Used by MCP tools/list, OpenAI tools manifest, and Anthropic tools manifest.
    """
    properties = {}
    required = []

    for arg in getattr(field, 'arguments', []):
        arg_name = getattr(arg, 'python_name', None) or getattr(arg, 'name', '')
        arg_desc = getattr(arg, 'description', '') or f'Parameter {arg_name}'
        arg_type = _gql_type_to_json(arg.type)

        properties[arg_name] = {'type': arg_type, 'description': arg_desc}

        if _is_required(arg.type):
            required.append(arg_name)

    return {'type': 'object', 'properties': properties, 'required': required}


class SchemaIntrospector:
    """
    Walks the live Strawberry schema and yields normalised field descriptors.
    All agentic surfaces (OpenAI, Anthropic, MCP, AgentOperator) use this class.
    """

    def __init__(self):
        from api.schema import get_schema

        self._schema = get_schema()

    def _iter_fields(self, type_name: Literal['Query', 'Mutation']):
        gql_type = self._schema.get_type_by_name(type_name)
        if not gql_type:
            return
        for field in gql_type.fields:
            name = field.name
            if name.startswith('_'):
                continue
            if type_name == 'Query' and name in _SKIP_QUERY_FIELDS:
                continue
            yield field

    def iter_query_fields(self):
        yield from self._iter_fields('Query')

    def iter_mutation_fields(self):
        yield from self._iter_fields('Mutation')

    # ── Format helpers ─────────────────────────────────────────────────────────

    def as_openai_tools(self) -> list[dict]:
        """Return a list of OpenAI function-calling tool definitions."""
        tools = []
        for prefix, iter_fn in [
            ('query', self.iter_query_fields),
            ('mutate', self.iter_mutation_fields),
        ]:
            for field in iter_fn():
                tools.append(
                    {
                        'type': 'function',
                        'function': {
                            'name': f'{prefix}_{field.name}',
                            'description': getattr(field, 'description', '')
                            or f'{prefix.capitalize()} {field.name}',
                            'parameters': build_field_schema(field),
                        },
                    }
                )
        return tools

    def as_anthropic_tools(self) -> list[dict]:
        """Return a list of Anthropic tool_use definitions."""
        return [
            {
                'name': t['function']['name'],
                'description': t['function']['description'],
                'input_schema': t['function']['parameters'],
            }
            for t in self.as_openai_tools()
        ]

    def as_mcp_tools(self) -> list[dict]:
        """Return a list of MCP-spec tool definitions."""
        tools = []
        for prefix, iter_fn in [
            ('query', self.iter_query_fields),
            ('mutate', self.iter_mutation_fields),
        ]:
            for field in iter_fn():
                tools.append(
                    {
                        'name': f'{prefix}_{field.name}',
                        'description': getattr(field, 'description', '')
                        or f'{prefix.capitalize()} {field.name}',
                        'inputSchema': build_field_schema(field),
                    }
                )
        return tools

    def as_agent_tool_map(self) -> dict:
        """Return an internal tool map used by AgentOperator."""
        tools = {}
        for field in self.iter_query_fields():
            tools[f'query_{field.name}'] = {
                'type': 'query',
                'field_name': field.name,
                'description': getattr(field, 'description', ''),
                'schema': build_field_schema(field),
            }
        for field in self.iter_mutation_fields():
            tools[f'mutate_{field.name}'] = {
                'type': 'mutation',
                'field_name': field.name,
                'description': getattr(field, 'description', ''),
                'schema': build_field_schema(field),
            }
        return tools
