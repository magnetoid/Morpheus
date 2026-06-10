---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:48'
updated: '2026-06-10T20:08:48'
---

# core/assistant/runtime.py

Symbols in `core/assistant/runtime.py`.

- L29 `_is_retriable(msg: str)` (function)
- L34 `_friendly_provider_error(raw: str)` (function) — Translate a raw provider exception into a user-readable line.
- L69 `AssistantMessage` (class)
- L78 `AssistantRunResult` (class)
- L88 `_format_recent_memories()` (function) — Compact bullet list of remembered facts, prepended each turn.
- L104 `_page_context_system(context: dict[str, Any] | None)` (function) — Compose the one-line system prefix carrying the URL+title of the
- L132 `_to_llm_messages(history: list[StoredMessage], user_message: str, *, context: dict[str, Any] | None=None)` (function) — Convert stored history + new user msg → LLMMessage objects from agents.llm.
- L177 `Assistant` (class) — Linda — the hardcoded staff AI assistant.
- L187 `__init__(self, *, provider=None, tools=None, store=None, max_steps: int | None=None)` (method)
- L198 `tools(self)` (method)
- L208 `run(self, *, message: str, conversation_key: str, context: dict[str, Any] | None=None)` (method) — Run one user turn; persist the exchange; return the result.
- L230 `stream(self, *, message: str, conversation_key: str, context: dict[str, Any] | None=None)` (method) — Generator that yields events as the turn progresses.
- L379 `_dispatch_tool(self, *, tc, tools_by_name, msgs, conversation_key, context)` (method) — Invoke a single tool call, persist the result, append to LLM context.
- L423 `run_assistant(*, message: str, conversation_key: str='default', context: dict[str, Any] | None=None)` (function) — Module-level convenience: run a single turn against the default Assistant.
