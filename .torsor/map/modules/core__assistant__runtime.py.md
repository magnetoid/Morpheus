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

# core/assistant/runtime.py

Symbols in `core/assistant/runtime.py`.

- L29 `_friendly_provider_error(raw: str)` (function) — Translate a raw provider exception into a user-readable line.
- L88 `AssistantRunResult` (class)
- L98 `_format_recent_memories(query: str='')` (function) — Compact bullet list of remembered facts, prepended each turn.
- L123 `_format_knowledge(query: str='')` (function) — Compact list of retrieved knowledge chunks, injected each turn.
- L148 `_format_janus_history(history: list[StoredMessage], *, limit: int=12)` (function) — A plain recap of recent turns for a fresh Janus session.
- L186 `_own_tools_prompt()` (function)
- L203 `_tool_events(conversation_key: str, since, seen: set)` (function) — Chat events for the tool calls the MCP edge recorded for this turn so far.
- L239 `Assistant` (class) — Linda — the staff AI assistant. Call :meth:`stream` to run one turn.
- L242 `__init__(self, *, store=None)` (method)
- L246 `_mode(context)` (method) — The EFFECTIVE mode for a turn, resolved server-side.
- L259 `_mint_turn_token(self, context, conversation_key: str)` (method) — A signed identity for this turn, or '' when there is no staff user.
- L287 `_turn_provider(context)` (method) — The provider and model this turn is wired to (the message's pick, the
- L302 `_system_prompt(self, *, context)` (method) — What stays the same from message to message, so the provider can cache it.
- L327 `_turn_context(self, *, message: str, context)` (method) — What belongs to this message only: the page it came from, and what the
- L341 `_finish(self, *, conversation_key: str, text: str, started: float, error: str='', usage: dict | None=None, tool_calls: int=0, turn: dict | None=None)` (method) — Store Linda's reply, with what the turn cost, and build the closing event.
- L401 `_record_run(*, conversation_key: str, turn: dict, text: str, error: str, model: str, prompt_tokens: int, completion_tokens: int, tool_calls: int, duration_ms: int)` (method) — One ``AgentRun`` per Janus turn, ``agent_name='linda'``.
- L450 `stream(self, *, message: str, conversation_key: str, context: dict[str, Any] | None=None)` (method) — Generator that yields events as the turn progresses.
- L592 `_emit_failure_signal(self, *, reason, conversation_key, detail='')` (method) — Phase 1d: record a Linda failure as a self-improvement signal so the
