---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/auth/services.py

Symbols in `core/auth/services.py`.

- L26 `_hash_code(*, code: str, email: str)` (function) — SHA-256 over (code || email) so a leaked DB doesn't leak codes.
- L32 `issue_otp(email: str, *, request_ip: str | None=None)` (function) — Issue a fresh OTP. Invalidates any prior unconsumed code for this email.
- L66 `consume_otp(email: str, code: str)` (function) — Verify a code + return the matching User (creating one if missing).
- L111 `send_otp_email(*, to: str, code: str)` (function) — Best-effort send of the OTP via the configured email backend.
