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

# core/authz.py

Symbols in `core/authz.py`.

- L42 `enforcement_mode()` (function) — Read the merchant's enforcement setting, fresh.
- L68 `has_capability(user, capability: str, *, channel=None)` (function) — True if `user` holds `capability` (optionally on `channel`).
- L103 `check(user, capability: str, *, channel=None, target: str='')` (function) — Run a capability check under the current enforcement mode.
- L123 `_audit_denial(user, capability: str, *, target: str, enforced: bool)` (function) — Record a denial (or a would-be denial) — never raise from the audit path.
- L148 `require_capability(capability: str, *, channel=None)` (function) — View decorator: gate a view on one capability.
- L182 `enforce(request, capability: str)` (function) — Imperative form of `require_capability`, for a view that READS with one
- L211 `_forbidden(request, capability: str)` (function)
