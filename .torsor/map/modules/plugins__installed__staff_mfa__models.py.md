---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/staff_mfa/models.py

Symbols in `plugins/installed/staff_mfa/models.py`.

- L17 `StaffMfaDevice` (class) — A staff user's enrolled TOTP authenticator (confirmed once a code verifies).
- L34 `__str__(self)` (method)
- L38 `is_confirmed(self)` (method)
- L42 `MfaRecoveryCode` (class) — One single-use recovery code, stored as a SHA-256 hash of a high-entropy token.
- L54 `__str__(self)` (method)
- L58 `is_used(self)` (method)
