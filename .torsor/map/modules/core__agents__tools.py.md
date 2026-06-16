---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/agents/tools.py

Symbols in `core/agents/tools.py`.

- L46 `ToolError` (class) — Raised by a tool to surface a clean, LLM-readable failure.
- L51 `ToolResult` (class) — The structured output of a tool call.
- L65 `Tool` (class) — A single capability an agent can invoke.
- L81 `to_openai_schema(self)` (method) — Render this tool as an OpenAI function-calling spec.
- L92 `to_anthropic_schema(self)` (method) — Render this tool as an Anthropic tool-use spec.
- L100 `invoke(self, arguments: dict[str, Any], **runtime_kwargs: Any)` (method) — Call the underlying handler, normalising the return type.
- L124 `tool(*, name: str, description: str, schema: dict[str, Any] | None=None, scopes: list[str] | None=None, requires_approval: bool=False)` (function) — Decorator that turns a plain function into a `Tool`.
