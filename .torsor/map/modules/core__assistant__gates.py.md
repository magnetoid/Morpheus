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

# core/assistant/gates.py

Symbols in `core/assistant/gates.py`.

- L80 `person_scopes(user)` (function) — Linda's profile, narrowed to what this person's role grants.
- L105 `automation_key(user_pk, automation_id)` (function) — The conversation a scheduled automation runs in, owned by its owner.
- L110 `is_automation_key(conversation_key: str)` (function)
- L120 `external_key(principal: str, chat: str)` (function) — The conversation an external agent's token holds with Janus.
- L125 `is_external_key(conversation_key: str)` (function)
- L129 `principal_of(conversation_key: str)` (function) — The token id an external conversation belongs to, or ''.
- L138 `gate_reason(*, tool, tool_name: str, args: dict, scopes, context: dict | None, conversation_key: str, human_message: str, spent_tokens: int=0, token_budget: int=0, human_message_at: float | None=None, needs_consent: bool | None=None, external_approved: frozenset[str] | None=None)` (function) — Return a refusal reason, or ``None`` to let the call through.
- L242 `is_write_tool(tool)` (function)
- L309 `linda_tool(tool, *, developer: bool=False)` (function) — Whether Linda is ever offered this tool, before her scope profile and mode:
- L319 `needs_consent(tool)` (function) — Whether a Linda call needs the merchant's own yes first.
- L334 `audit_write_tool(*, tool, args, payload, error_msg: str, conversation_key: str, user, is_write: bool | None=None)` (function) — Record a write-tool attempt to core.audit (fail-soft). Reads are skipped.
- L371 `latest_human_turn(conversation_key: str)` (function) — The newest ``role='user'`` message stored for a conversation, and when it was sent.
