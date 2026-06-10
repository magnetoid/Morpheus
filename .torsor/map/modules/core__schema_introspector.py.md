---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# core/schema_introspector.py

Symbols in `core/schema_introspector.py`.

- L25 `_gql_type_to_json(gql_type)` (function) — Walk a possibly-wrapped type (NonNull, List) to find the leaf scalar name.
- L36 `_is_required(arg_type)` (function) — A GraphQL argument is required when the outermost wrapper is NonNull.
- L43 `build_field_schema(field)` (function) — Build a JSON Schema 'object' describing the arguments of a single GraphQL field.
- L64 `SchemaIntrospector` (class) — Walks the live Strawberry schema and yields normalised field descriptors.
- L70 `__init__(self)` (method)
- L74 `_iter_fields(self, type_name: Literal['Query', 'Mutation'])` (method)
- L86 `iter_query_fields(self)` (method)
- L89 `iter_mutation_fields(self)` (method)
- L94 `as_openai_tools(self)` (method) — Return a list of OpenAI function-calling tool definitions.
- L110 `as_anthropic_tools(self)` (method) — Return a list of Anthropic tool_use definitions.
- L121 `as_mcp_tools(self)` (method) — Return a list of MCP-spec tool definitions.
- L134 `as_agent_tool_map(self)` (method) — Return an internal tool map used by AgentOperator.
