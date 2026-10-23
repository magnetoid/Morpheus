---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/agents/tools.py

Symbols in `core/agents/tools.py`.

- L46 `ToolError` (class) — Raised by a tool to surface a clean, LLM-readable failure.
- L51 `ToolResult` (class) — The structured output of a tool call.
- L65 `Tool` (class) — A single capability an agent can invoke.
- L88 `api_name(self)` (method) — Provider-safe spelling of `name`.
- L100 `to_openai_schema(self)` (method) — Render this tool as an OpenAI function-calling spec.
- L111 `to_anthropic_schema(self)` (method) — Render this tool as an Anthropic tool-use spec.
- L119 `invoke(self, arguments: dict[str, Any], **runtime_kwargs: Any)` (method) — Call the underlying handler, normalising the return type.
- L158 `tool(*, name: str, description: str, schema: dict[str, Any] | None=None, scopes: list[str] | None=None, requires_approval: bool=False, supports_staging: bool=False)` (function) — Decorator that turns a plain function into a `Tool`.
