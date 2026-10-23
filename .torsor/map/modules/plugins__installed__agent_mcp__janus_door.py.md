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

# plugins/installed/agent_mcp/janus_door.py

Symbols in `plugins/installed/agent_mcp/janus_door.py`.

- L52 `DoorError` (class)
- L53 `__init__(self, code: str, message: str)` (method)
- L59 `token_entry(token_id: str)` (function) — The token's entry, read fresh, so a revoked token stops at once.
- L76 `janus_granted(entry: Any, surface: str='mcp')` (function) — Whether the merchant let this token talk to Janus on ``surface``.
- L84 `_turn_key(turn_id: str)` (function)
- L88 `_running_key(token_id: str)` (function)
- L92 `_wait_seconds(value: Any)` (function)
- L101 `ask(*, entry: Any, message: str, conversation: str='', wait_seconds: Any=None, surface: str='mcp')` (function) — Queue a question for Janus and wait a little for the answer.
- L167 `reply(*, entry: Any, turn: str, wait_seconds: Any=None, surface: str='mcp')` (function) — The answer to an earlier question, waiting a little if it is still running.
- L177 `wait(*, turn_id: str, token_id: str, wait_seconds: Any=None)` (function)
- L191 `_running(token_id: str)` (function)
- L202 `_public(state: dict)` (function)
- L221 `_save(state: dict, **changes: Any)` (function)
- L228 `run(turn_id: str, message: str)` (function) — Worker side: run a queued turn. Returns its final status.
- L272 `door_tools()` (function)
- L335 `_mcp_caller()` (function)
- L341 `_refused(error: DoorError)` (function)
- L345 `_mcp_ask(message: str, conversation: str='', wait_seconds: int | None=None)` (function)
- L358 `_mcp_reply(turn: str, wait_seconds: int | None=None)` (function)
