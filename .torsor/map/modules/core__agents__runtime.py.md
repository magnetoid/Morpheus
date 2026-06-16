---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/agents/runtime.py

Symbols in `core/agents/runtime.py`.

- L50 `RunResult` (class)
- L60 `_to_json_for_llm(value: Any)` (function) — Serialise a tool's output so the LLM can read it back.
- L68 `AgentRuntime` (class) — Runs one agent against one user message.
- L75 `__init__(self, agent: MorpheusAgent, *, provider: LLMProvider | None=None, on_step: Callable[[TraceStep], None] | None=None, approval_check: Callable[[Tool, dict[str, Any]], bool] | None=None)` (method)
- L90 `run(self, *, user_message: str, history: list[LLMMessage] | None=None, context: dict[str, Any] | None=None, run_id: str | None=None)` (method) — Run the agent against `user_message`. Returns when the loop completes.
- L198 `_dispatch_tool(self, *, tc: LLMToolCall, tools_by_name: dict[str, Tool], trace: AgentTrace, messages: list[LLMMessage], context: dict[str, Any], run_id: str)` (method)
- L306 `_tool_back(self, trace: AgentTrace, messages: list[LLMMessage], tc: LLMToolCall, *, error: str)` (method) — Send an error back to the LLM as a tool result so it can recover.
- L334 `_fail(self, trace: AgentTrace, run_id: str, context: dict[str, Any], error: str)` (method)
- L360 `_on_end(self, run_id: str, context: dict[str, Any], result: RunResult)` (method)
- L367 `_humanise_provider_error(exc: Exception)` (function) — Turn a raw provider exception into a short, actionable chat message.
