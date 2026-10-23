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

# core/assistant/tests/test_turn_identity.py

Symbols in `core/assistant/tests/test_turn_identity.py`.

- L16 `_user(pk=7)` (function)
- L20 `TurnTokenTests` (class)
- L21 `test_round_trip(self)` (method)
- L28 `test_prefix_distinguishes_it_from_api_keys(self)` (method)
- L34 `test_tampering_is_detected(self)` (method)
- L38 `test_expiry(self)` (method)
- L43 `test_tokens_are_unique_per_turn(self)` (method)
- L48 `test_another_secret_key_cannot_forge_one(self)` (method)
- L55 `ResolveUserTests` (class)
- L56 `setUp(self)` (method)
- L61 `_identity(self)` (method)
- L65 `test_active_staff_resolves(self)` (method)
- L68 `test_non_staff_does_not_resolve(self)` (method)
- L74 `test_deactivated_user_does_not_resolve(self)` (method)
- L81 `MintForTurnTests` (class) — What Assistant hands the engine.
- L84 `test_no_staff_user_means_no_token(self)` (method)
- L93 `test_staff_user_gets_a_token_for_their_conversation_and_resolved_mode(self)` (method)
