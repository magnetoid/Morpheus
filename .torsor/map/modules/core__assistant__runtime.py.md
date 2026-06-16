---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/assistant/runtime.py

Symbols in `core/assistant/runtime.py`.

- L39 `_is_retriable(msg: str)` (function)
- L44 `_friendly_provider_error(raw: str)` (function) — Translate a raw provider exception into a user-readable line.
- L88 `AssistantMessage` (class)
- L97 `AssistantRunResult` (class)
- L107 `_format_recent_memories()` (function) — Compact bullet list of remembered facts, prepended each turn.
- L124 `_page_context_system(context: dict[str, Any] | None)` (function) — Compose the one-line system prefix carrying the URL+title of the
- L152 `_to_llm_messages(history: list[StoredMessage], user_message: str, *, context: dict[str, Any] | None=None)` (function) — Convert stored history + new user msg → LLMMessage objects from agents.llm.
- L201 `Assistant` (class) — Linda — the hardcoded staff AI assistant.
- L211 `__init__(self, *, provider=None, tools=None, store=None, max_steps: int | None=None)` (method)
- L223 `tools(self)` (method)
- L234 `run(self, *, message: str, conversation_key: str, context: dict[str, Any] | None=None)` (method) — Run one user turn; persist the exchange; return the result.
- L255 `stream(self, *, message: str, conversation_key: str, context: dict[str, Any] | None=None)` (method) — Generator that yields events as the turn progresses.
- L435 `_dispatch_tool(self, *, tc, tools_by_name, msgs, conversation_key, context)` (method) — Invoke a single tool call, persist the result, append to LLM context.
- L491 `run_assistant(*, message: str, conversation_key: str='default', context: dict[str, Any] | None=None)` (function) — Module-level convenience: run a single turn against the default Assistant.
