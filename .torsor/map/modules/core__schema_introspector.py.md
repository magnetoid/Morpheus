---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/schema_introspector.py

Symbols in `core/schema_introspector.py`.

- L27 `_gql_type_to_json(gql_type)` (function) — Walk a possibly-wrapped type (NonNull, List) to find the leaf scalar name.
- L38 `_is_required(arg_type)` (function) — A GraphQL argument is required when the outermost wrapper is NonNull.
- L45 `build_field_schema(field)` (function) — Build a JSON Schema 'object' describing the arguments of a single GraphQL field.
- L66 `SchemaIntrospector` (class) — Walks the live Strawberry schema and yields normalised field descriptors.
- L72 `__init__(self)` (method)
- L77 `_iter_fields(self, type_name: Literal['Query', 'Mutation'])` (method)
- L89 `iter_query_fields(self)` (method)
- L92 `iter_mutation_fields(self)` (method)
- L97 `as_openai_tools(self)` (method) — Return a list of OpenAI function-calling tool definitions.
- L118 `as_anthropic_tools(self)` (method) — Return a list of Anthropic tool_use definitions.
- L129 `as_mcp_tools(self)` (method) — Return a list of MCP-spec tool definitions.
- L147 `as_agent_tool_map(self)` (method) — Return an internal tool map used by AgentOperator.
