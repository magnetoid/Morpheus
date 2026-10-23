---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/agent_core/services.py

Symbols in `plugins/installed/agent_core/services.py`.

- L26 `_run_with_timeout(*, runtime, user_message, history, context, run_id, timeout)` (function) — Execute `runtime.run(...)` on a worker thread; raise TimeoutError on cap.
- L88 `_persist_step(*, run, seq: int, step: TraceStep)` (function)
- L130 `run_agent(*, agent_name: str, user_message: str, customer: Any | None=None, session_key: str='', history: Iterable[LLMMessage] | None=None, context: dict[str, Any] | None=None, conversation_id: str | None=None, on_step: Any=None)` (function) — Run a registered agent and persist the trace.
- L293 `invocation_denial(agent: MorpheusAgent, request: Any)` (function) — Why the caller behind `request` may NOT invoke `agent` ('' = allowed).
- L330 `history_for_conversation(conversation_id: str, *, limit: int=20)` (function) — Load the recent messages of a conversation as `LLMMessage` history.
