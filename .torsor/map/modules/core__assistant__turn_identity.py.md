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

# core/assistant/turn_identity.py

Symbols in `core/assistant/turn_identity.py`.

- L40 `TurnIdentity` (class)
- L55 `is_turn_token(token: str)` (function)
- L59 `mint(*, user, conversation_key: str, mode_slug: str, ttl_s: int, provider: str='', model: str='', principal: str='')` (function) — Sign a token for one turn. ``ttl_s`` should cover the turn timeout.
- L87 `verify(token: str)` (function) — The identity a token carries, or None if it is forged, malformed or expired.
- L120 `resolve_user(identity: TurnIdentity)` (function) — The staff user behind a turn, or None if they are no longer staff/active.
