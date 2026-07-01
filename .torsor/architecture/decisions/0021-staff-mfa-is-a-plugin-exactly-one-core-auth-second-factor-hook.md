---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-24T02:15:08'
updated: '2026-06-24T02:15:08'
rules:
- id: new-login-path-must-run-second-factor
  pattern: pre_social_login|SocialAccountAdapter|auth_login\(|auth\.login\(
  message: New sign-in path? It MUST fire the staff_mfa second-factor gate
    (staff_mfa.services.second_factor_response → ImmediateHttpResponse to the TOTP
    challenge). allauth/SSO/social providers call their OWN login() and do NOT fire
    core's AUTH_SECOND_FACTOR hook, so they log in single-factor. (ADR 0021; the
    MFA-bypass landmine in CLAUDE.md.)
- id: single-core-second-factor-hook
  pattern: AUTH_SECOND_FACTOR
  message: Exactly ONE core second-factor extension point — the AUTH_SECOND_FACTOR
    filter fired in core/auth otp_verify (after email-OTP, before login()). Don't
    add a parallel second-factor hook; all MFA logic lives in plugins/installed/staff_mfa.
    (ADR 0021.)
---

# ADR 0021: Staff MFA is a plugin + exactly one core AUTH_SECOND_FACTOR hook

## Context
Staff sign-in was single-factor passwordless email-OTP (core/auth). The 2026 competitive/security fact-check rated this the top enterprise/trust gap (the only confirmed-real, already-specced P0). Project policy (ADR 0011-adjacent user-management rule): keep core auth simple — SSO/MFA/RBAC/teams ship as plugins, not core. core/auth is a PROTECTED_PATH in core/safety.py (the self-improvement engine cannot auto-edit it).

## Decision
MFA ships as plugins/installed/staff_mfa (TOTP via pyotp>=2.9). Core gains exactly ONE extension point: an AUTH_SECOND_FACTOR filter (core/hooks.py) fired in core/auth/otp_verify AFTER email-OTP (factor one) succeeds and BEFORE login(); a subscriber returning an HttpResponse interposes a challenge, else login proceeds unchanged. The plugin owns enrollment (QR+confirm), the session-gated public challenge view, SHA-256 single-use recovery codes, rate-limiting (5/15min on challenge AND enroll-confirm), require_for_staff enforcement, and an audited break-glass `manage.py reset_mfa`. Forks resolved: pyotp over allauth.mfa (fits the custom email-OTP flow); opt-in rollout (require_for_staff=False) registered in MORPHEUS_DEFAULT_PLUGINS. TOTP secret stored as a plain model field (no encryption helper exists in-repo; matches PluginConfig's plaintext posture) but never logged/serialized to assistant/API/webhooks. Shipped v0.2.7, commit b656e0b on feat/staff-mfa (not pushed).

## Consequences
Disabling staff_mfa removes the AUTH_SECOND_FACTOR subscriber → sign-in reverts to single-factor email-OTP exactly (disable-test clean). Contract test caught a real bug: Customer PK is a UUID, so the pending-user session value must be str()'d or the JSON session serializer 500s the challenge redirect. Known follow-ups (documented in docs/plans/staff-mfa.md): (1) hard per-request enforcement of unenrolled-but-required staff needs a plugin middleware (current enforcement is login-time/soft) — needs a plugin-middleware contribution API that does not exist yet; (2) at-rest encryption of the TOTP seed; (3) recovery codes are 40-bit (rate-limit-bounded). SSO (SAML/OIDC) remains absent — the natural next enterprise-security gap. New constraint: all 2FA/MFA logic stays in plugins/installed/staff_mfa; core exposes only the AUTH_SECOND_FACTOR hook and must not import the plugin.
