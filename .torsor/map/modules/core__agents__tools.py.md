---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# core/agents/tools.py

Symbols in `core/agents/tools.py`.

- L44 `ToolError` (class) — Raised by a tool to surface a clean, LLM-readable failure.
- L49 `ToolResult` (class) — The structured output of a tool call.
- L62 `Tool` (class) — A single capability an agent can invoke.
- L77 `to_openai_schema(self)` (method) — Render this tool as an OpenAI function-calling spec.
- L88 `to_anthropic_schema(self)` (method) — Render this tool as an Anthropic tool-use spec.
- L96 `invoke(self, arguments: dict[str, Any], **runtime_kwargs: Any)` (method) — Call the underlying handler, normalising the return type.
- L120 `tool(*, name: str, description: str, schema: dict[str, Any] | None=None, scopes: list[str] | None=None, requires_approval: bool=False)` (function) — Decorator that turns a plain function into a `Tool`.
