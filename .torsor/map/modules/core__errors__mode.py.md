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

# core/errors/mode.py

Symbols in `core/errors/mode.py`.

- L28 `_read_until()` (function)
- L35 `detailed_until()` (function) — When detailed capture ends, or None when it is off. Fail-soft.
- L56 `detailed_active()` (function)
- L60 `forget()` (function) — Drop the memo, so this process reads the switch on its next check.
- L67 `turn_on(hours: int, *, user=None)` (function)
- L88 `turn_off(*, user=None)` (function)
- L96 `state()` (function) — What the error log page shows about the switch.
- L113 `_audit(event: str, user, metadata: dict)` (function)
