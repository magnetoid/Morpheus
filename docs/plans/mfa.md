# MFA (TOTP) — spec

## Context

F10 (security hardening) asked for MFA. Verified state: there is **none** today
(no `pyotp`, no TOTP code anywhere). The other F10 items are already covered —
the `core.auth` email-OTP login has lockout (429 + 15-min email lock + per-hour
cap), API tokens are hashed, and the audit-log surface shipped (`a9388fa`). MFA
is the one real remaining piece.

This is **security-critical** and **auth-flow-touching**, so it gets its own
careful build, not a tail-of-session rush. House rule: **MFA ships as a plugin**,
not core (core auth stays simple; SSO/MFA/RBAC are plugins).

## Dependency (Verified-Output rule)

Add **`pyotp`** (PyPI, ~2k stars, the standard Python TOTP lib; pure-Python, no
native deps). Justify in the commit. **Avoid a `qrcode` dep** — render the QR
client-side from the `otpauth://` URI (e.g. a tiny JS QR lib already vendored, or
an `<img>` to a data-URI generated in-browser), so the only new server dep is
`pyotp`. Confirm `pyotp` is on PyPI and pin it in requirements before coding.

## Models (new `mfa` plugin, `plugins/installed/mfa/`)

```
MfaDevice
  user (OneToOne AUTH_USER_MODEL) · secret (CharField, the base32 TOTP seed)
  confirmed (bool) · created_at · last_used_at
RecoveryCode
  user (FK) · code_hash (sha256, like the API-token pattern) · used_at (nullable)
```

Secrets at rest: the seed is sensitive — store it, but note it in the
encrypt-secrets-at-rest backlog (Fernet) alongside the AI provider keys / SMTP
password. v1 may ship plaintext-in-db with a TODO; flag it explicitly.

## Flows

1. **Enrol** (dashboard page, `/dashboard/security/mfa/`): generate a secret →
   show the `otpauth://totp/...` QR + manual key → user enters a current code →
   verify with `pyotp.TOTP(secret).verify(code, valid_window=1)` → set
   `confirmed=True` → **show 10 one-time recovery codes** (display once; store
   only hashes).
2. **Verify at login**: after the primary login succeeds, if the user has a
   confirmed device, require a TOTP (or recovery) code before access. On success
   set `request.session['mfa_verified'] = True`.
3. **Gate**: middleware (registered by the plugin) that, for **session-authed
   staff hitting `/dashboard/`**, redirects to the verify page when the user has
   a confirmed device and `mfa_verified` is not set. **Must NOT gate**: the OTP
   login views themselves, the MFA verify/enrol pages, API/MCP **Bearer-token**
   auth (those carry their own scoped auth), or anonymous requests.
4. **Recovery / reset**: a recovery code consumes (marks `used_at`) and passes
   the gate once. A `manage.py mfa_reset --user <email>` superuser command
   removes a device — the documented break-glass path so no one is ever locked
   out by a lost authenticator.

## Settings

- Per-user opt-in by default. A plugin setting `enforce_mfa_for_staff` (default
  off) that, when on, blocks dashboard access until staff enrol (with a grace
  banner, not a hard wall, on first rollout).

## Surfaces / contributions

- `contribute_dashboard_pages`: "Security / MFA" under `developer` or `access`.
- `register_urls`: enrol, verify, disable, regenerate-recovery.
- Middleware via the plugin's `ready()` (or a `register_middleware` hook if one
  exists; else document the one settings entry).
- `core.audit`: record `mfa.enrolled`, `mfa.verified`, `mfa.recovery_used`,
  `mfa.reset` — they'll show in the new audit log.

## Risks (read before coding)

- **Lockout is the #1 risk.** Recovery codes + the `mfa_reset` command are
  mandatory, not optional. Test the break-glass path first.
- **Gate scope.** A too-broad middleware can lock out the login flow itself or
  break token auth. Whitelist the auth/enrol/verify URLs and exempt Bearer-auth.
- **Don't enforce org-wide by default.** Opt-in; enforcement is a deliberate
  merchant choice with a grace period.
- **Clock skew.** `valid_window=1` (±30s). Document.
- **Secret at rest.** Plaintext seed is a real exposure — link the
  encrypt-secrets-at-rest work; ideally land Fernet first or together.

## Verification

- Unit: enrol confirms only on a valid code; recovery code single-use; reset
  command removes the device.
- Gate tests (permission-boundary discipline): staff with confirmed device + no
  `mfa_verified` → redirected; after verify → allowed; **Bearer-token request →
  never gated**; anonymous → unaffected; login/enrol/verify URLs → never gated.
- `DATABASE_URL='sqlite:///:memory:'` for tests; CI Postgres for the migration.
- Smoke: enrol with a real authenticator app against the live URL before
  enabling `enforce_mfa_for_staff`.
