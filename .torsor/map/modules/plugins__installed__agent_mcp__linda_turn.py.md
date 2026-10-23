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

# plugins/installed/agent_mcp/linda_turn.py

Symbols in `plugins/installed/agent_mcp/linda_turn.py`.

- L36 `ExternalGrant` (class) — What an external agent's API token may do, read fresh on every call.
- L46 `LindaTurn` (class)
- L59 `turn_for_request(request)` (function) — The verified turn behind a request's Bearer token, or None. Cached per request.
- L69 `_resolve(request)` (function)
- L107 `_external_for(identity)` (function) — The token grant an external turn runs under: None for a merchant's own
- L122 `_external_grant(token_id: str)` (function)
- L137 `scope_profile(turn: LindaTurn)` (function) — Linda's scope profile, narrowed to the person or to an external agent's token.
- L171 `_all_tools()` (function) — Linda's built-in tools plus every tool an app registered (first name wins).
- L182 `catalogue(turn: LindaTurn)` (function) — Every tool this turn may see and call: Linda's profile, then the mode.
- L197 `mode_tools(tools: list, turn: LindaTurn)` (function) — The part of a catalogue a turn's mode allows.
- L204 `needs_consent(tool)` (function) — Whether a Linda call needs the merchant's own yes first (core/assistant/gates.py).
- L209 `call_tool(tool, name: str, args: dict, turn: LindaTurn, *, audit_call, audit_denied)` (function) — Run the gate chain, then the tool. Returns an MCP ``tools/call`` result.
- L286 `_result(output: Any, *, is_error: bool)` (function)
- L296 `_remember(conversation_key: str, name: str, args: dict, output: Any)` (function) — Record the call in the conversation, as the in-process loop did.
