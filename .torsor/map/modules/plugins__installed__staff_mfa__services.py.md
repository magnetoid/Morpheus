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

# plugins/installed/staff_mfa/services.py

Symbols in `plugins/installed/staff_mfa/services.py`.

- L26 `new_secret()` (function)
- L32 `provisioning_uri(secret: str, *, account: str, issuer: str)` (function) — The otpauth:// URI an authenticator app scans to add the account.
- L41 `verify_totp(secret: str, code: str)` (function)
- L52 `_hash_code(code: str)` (function)
- L56 `generate_recovery_codes(device, *, count: int=_RECOVERY_CODE_COUNT)` (function) — Replace any existing codes with `count` fresh ones; return the PLAINTEXT
- L69 `consume_recovery_code(device, code: str)` (function) — Burn one matching unused recovery code. Returns True on success.
- L84 `qr_svg(data: str, *, box: int=5)` (function) — Render `data` as an inline SVG QR code (no PIL/lxml needed).
- L107 `_client_ip(request)` (function)
- L116 `audit(event_type: str, *, actor=None, target: str='', request=None, metadata=None, severity='info')` (function) — Record an mfa.* audit event. Never raises (core.audit swallows DB errors).
- L133 `second_factor_response(plugin, request, user, nxt: str)` (function) — Return an HttpResponse to interpose, or None to let login proceed.
