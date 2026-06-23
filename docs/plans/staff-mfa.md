# Staff MFA (two-factor authentication) — spec

Status: **implemented in v0.2.7** (`plugins/installed/staff_mfa/` + the one core
hook). Both forks resolved as recommended: **`pyotp`** for TOTP, and **opt-in**
rollout (`require_for_staff=False`). As-built deltas from the draft are noted
inline below (secret-at-rest posture; soft vs hard enforcement).

## Problem
Staff/admin sign-in is **single-factor**: a one-time code emailed to the address
(`core/auth`, passwordless email-OTP). Whoever controls — or intercepts — that
inbox gets the full dashboard/admin. The audit fact-check rates this the top
security gap and an enterprise/trust blocker. We add a second, independent factor
for staff so an account takeover needs *both* the email **and** an enrolled device.

## Anchoring decision: MFA is a PLUGIN; core gets one hook
Project policy (CLAUDE.md "user management"; memory `feedback_user_management`):
**keep core auth simple — SSO/MFA/RBAC/teams ship as plugins.** So MFA does **not**
go in `core`. It ships as `plugins/installed/staff_mfa/`. `core/auth` gains exactly
one extension point — a filter fired after the email-OTP succeeds, before the
session is established — that the plugin uses to interpose a TOTP challenge.
Disable the plugin → the hook has no subscriber → login proceeds exactly as today
(disable-test clean).

## Goals
- TOTP second factor (authenticator apps) for **staff** (`is_staff`).
- Self-service enrollment (QR + confirm) and one-time **recovery codes**.
- Configurable enforcement: **opt-in → required-for-staff**.
- Admin "reset MFA" so a lost device never permanently bricks an account.
- Zero behaviour change for customers, and for the current flow when the plugin
  is disabled or the user isn't enrolled (opt-in phase).

## Non-goals (this iteration)
- WebAuthn / passkeys (clean follow-up once TOTP ships).
- MFA for storefront customers (scope to staff first).
- SMS factor (phishable / SIM-swap — skip).

## Second factor library: `pyotp` (chosen)
**Resolved → `pyotp` (`>=2.9`, added to `requirements.txt`).** Tiny, ubiquitous,
RFC-6238; standalone, so it fits the custom email-OTP flow with no allauth-flow
assumptions. The contract test hits its real interface (not a mock).
`allauth.mfa` was rejected: it hooks allauth's *password* login, not our parallel
email-OTP flow, so wiring it into `otp_verify` would have been awkward.

## Core extension point (the only `core` change)
In `core/auth/views.py:otp_verify`, at the success branch (today `login(request,
user)` at line 165), fire a filter before establishing the session:

```python
resp = hook_registry.filter('AUTH_SECOND_FACTOR', value=None,
                            request=request, user=user, next=nxt)
if resp is not None:
    return resp            # a subscriber interposed a challenge response
login(request, user)       # else: unchanged from today
```

Register `AUTH_SECOND_FACTOR` in `core.hooks`. ~6 lines in core; **all** MFA logic
lives in the plugin. With no subscriber the behaviour is byte-identical to today.

## Plugin: `plugins/installed/staff_mfa/`
- **models.py**: `StaffMfaDevice(user OneToOne, secret, confirmed_at, last_used_at,
  created_at)` and `MfaRecoveryCode(device FK, code_hash, used_at, created_at)`.
  Recovery codes are **SHA-256 hashed**, never stored plaintext (single-use).
  **As-built — TOTP secret at rest:** the platform has *no* field-encryption helper
  (API keys live plaintext in `PluginConfig` today), so to match that posture the
  base32 seed is stored as a plain model field — but it is **never exposed to the
  assistant** (the plugin contributes no agent tool over these models), nor to the
  public API, logs, or webhooks. At-rest *encryption* of the seed is a documented
  follow-up, deliberately not invented here (simplicity-first / match-existing).
- **AUTH_SECOND_FACTOR subscriber** (`apps.py:ready()`): if `user.is_staff` and
  (a confirmed device exists OR enforcement requires one) → stash pending user id +
  `next` in the session and return `redirect()` to the challenge view; else return
  `None`.
- **Challenge view**: prompt for a 6-digit TOTP **or** a recovery code;
  rate-limited via `core/ratelimit` (5 tries → lock, mirroring the OTP lockout);
  on success calls `login(request, user)` and redirects to `next`.
- **Enrollment page** (Settings → Security → Two-factor, via a dashboard-page
  contribution behind `{% plugin_enabled "staff_mfa" %}`): render the `otpauth://`
  QR, confirm a code to activate, reveal one-time recovery codes once.
- **Settings panel**: `require_for_staff` (bool, default **False** for rollout),
  issuer label.
- **Admin reset**: a staff/superuser action to clear another user's `MfaDevice`,
  written to `core.audit` (`mfa.*` events — the audit prefix already reserved in
  `observability/views.py`).

## Flow
- **Enroll**: staff → Two-factor → scan QR → enter code to confirm → store device +
  show recovery codes once.
- **Login**: email → email-OTP (factor 1, unchanged) → if staff + enrolled, the
  plugin interposes the TOTP challenge (factor 2) → verify → session established.
- **Recover**: a recovery code substitutes for TOTP (marked used). Lost device +
  no codes → another admin resets the device.

## Enforcement / rollout
- **Phase A** — plugin enabled, opt-in: staff may enroll; unenrolled staff log in
  as today.
- **Phase B** — flip `require_for_staff=True`: unenrolled staff are routed to
  enrollment **at sign-in**. **First-admin grace**: enforcement applies only once
  ≥1 device exists org-wide, so the first admin can't lock everyone out; the
  `reset_mfa` management command is the break-glass.
  **As-built — enforcement is currently login-time (soft).** Enrolled staff are
  *hard*-gated (login cannot complete without TOTP). Unenrolled-but-required staff
  are redirected to enrollment at the sign-in boundary; hard per-request gating of
  every dashboard URL (so they can't navigate away unenrolled) needs a plugin
  middleware and is the documented Phase-B follow-up.

## Phases (each with a verify step)
1. **Core hook** — add `AUTH_SECOND_FACTOR` filter + fire it in `otp_verify`.
   *Verify*: existing `core/auth` tests pass; with no subscriber, login is unchanged.
2. **Plugin scaffold** — `plugin-skeleton` (apps/plugin/models/migration/tests) +
   register in `MORPHEUS_DEFAULT_PLUGINS` (OFF by default initially? — see CHOICE
   below). *Verify*: `makemigrations --check` clean; disable test green.
3. **Enroll + challenge + recovery + rate-limit**. *Verify*: enroll → logout →
   login requires TOTP; wrong code is rate-limited; a recovery code works once.
4. **Enforcement setting + admin reset + audit events**. *Verify*: `require_for_staff`
   routes unenrolled staff to enrollment; reset clears a device (audited); the
   first admin can't brick the org.

## Tests (mandatory)
- The **three permission-boundary tests** on the challenge, enrollment, and reset
  views (anon blocked / authed-without-scope blocked / staff-with-scope allowed) —
  per the `permission-boundary-tests` skill.
- **TOTP contract** (hit `pyotp`'s real interface, not a mock): correct code passes;
  wrong code fails *and* counts toward lockout; recovery code is single-use; a
  replayed/expired code is rejected.
- **Disable test**: `staff_mfa` off → no challenge, no panel, login = current flow.

## Risks / landmines
- **Bricking the only admin** → enforcement needs the first-device grace + a reset
  path (management command) before Phase B flips.
- **TOTP brute force** → rate-limit the challenge (6 digits = 1e6 space).
- **Secret at rest** → never logged, never exposed to the assistant/API/webhooks;
  stored as a plain field matching the platform's existing secret posture
  (at-rest encryption is a documented follow-up — see models.py note above).
- Don't regress the email-OTP lockout — the second factor is **additive**, after
  OTP success.
- **Migration** → nullable additions only; no cross-type FK retarget (the
  sqlite-masks-Postgres landmine).

## Rollout: registered + opt-in (chosen)
**Resolved →** `staff_mfa` is registered in `MORPHEUS_DEFAULT_PLUGINS` and ships
**opt-in** (`require_for_staff=False`): present and enrollable without forcing a
flow change on existing staff. Enforcement is flipped deliberately in Phase B.

## Success criteria
- A staff user can enroll TOTP and is then required to provide it at every login.
- A wrong TOTP is rate-limited; a recovery code works once; an admin can reset a
  lost device (audited).
- Customers and unenrolled staff (opt-in phase) see no change; disabling
  `staff_mfa` removes every MFA surface and login reverts to today's flow.
