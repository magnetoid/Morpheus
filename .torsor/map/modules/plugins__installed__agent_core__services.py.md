---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/agent_core/services.py

Symbols in `plugins/installed/agent_core/services.py`.

- L26 `_run_with_timeout(*, runtime, user_message, history, context, run_id, timeout)` (function) — Execute `runtime.run(...)` on a worker thread; raise TimeoutError on cap.
- L82 `_persist_step(*, run, seq: int, step: TraceStep)` (function)
- L120 `run_agent(*, agent_name: str, user_message: str, customer: Any | None=None, session_key: str='', history: Iterable[LLMMessage] | None=None, context: dict[str, Any] | None=None, conversation_id: str | None=None, on_step: Any=None)` (function) — Run a registered agent and persist the trace.
- L284 `history_for_conversation(conversation_id: str, *, limit: int=20)` (function) — Load the recent messages of a conversation as `LLMMessage` history.
