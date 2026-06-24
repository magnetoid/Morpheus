# Staff SSO (SAML / OIDC) — spec

Status: **Phases 1–3 implemented** on `feat/staff-sso` (plugin
`plugins/installed/staff_sso/`, OFF by default). Forks decided: **OIDC first**
(no SAML this build), **email-domain allowlist + optional group claim**
staff-gating, **dashboard settings panel** for provider config. Phase 4 (SAML
provider + login-button UI + further `sso.*` audit polish) remains open.
Sibling to staff MFA (`docs/plans/staff-mfa.md`) — same "auth stays simple in
core; SSO ships as a plugin" policy.

Settings.py edits this build required (Django's app registry is frozen after
settings import, so the provider app cannot be added from `ready()`):
`plugins.installed.staff_sso` added to `MORPHEUS_DEFAULT_PLUGINS`, and
`allauth.socialaccount.providers.openid_connect` added to `THIRD_PARTY_APPS`
(inert without a configured `SocialApp`). The OIDC provider hard-imports
`pyjwt[crypto]` (allauth's `[socialaccount]` extra) at app load, so that dep was
added to `requirements.txt` — without it the provider app crashes boot.

## Problem
Staff sign-in is email-OTP only. Enterprise buyers require federated SSO
(SAML 2.0 / OIDC) against their IdP (Okta, Azure AD / Entra, Google Workspace)
so staff use corporate credentials + central de-provisioning. The fact-checks
rate SSO the joint-P0 enterprise unblock alongside MFA (now shipped).

## Anchoring decision: a thin plugin over the already-installed allauth
`django-allauth` **65.17.0 is already a dependency** (`requirements.txt`), with
`allauth.account` + `allauth.socialaccount` enabled, and the **OIDC**
(`allauth.socialaccount.providers.openid_connect`) and **SAML**
(`allauth.socialaccount.providers.saml`) providers available. So we do **not**
build SAML/OIDC protocol code — SSO is a **~400–500-line config + glue plugin**
(`plugins/installed/staff_sso/`) that:
- enables an allauth social provider, configured from a dashboard settings panel;
- JIT-provisions a `customers.Customer` from the IdP assertion via a thin
  `SocialAccountAdapter`;
- staff-gates (domain allowlist / group claim);
- **closes the SSO-bypasses-MFA hole** (see §Security — the critical bit).
Disable the plugin → no provider registered → login reverts to email-OTP
(disable-test clean). No new protocol dependency.

## Goals
- Staff sign in via the org IdP (OIDC first; SAML close behind).
- JIT provisioning: first SSO login creates/links a `Customer` by email.
- Staff-gating: only the right people get in (and get `is_staff`).
- **SSO logins honour the staff MFA second factor** (no bypass).
- Zero change for customers and for email-OTP when the plugin is disabled.

## Non-goals (this iteration)
- SCIM auto-provisioning/de-provisioning (JIT only for now).
- Customer-facing social login (Google/Facebook "sign in") — this is *staff* SSO.
- Per-tenant multi-IdP (one IdP config to start; model allows growth).

## How login works today (verified)
- Email-OTP: `core/auth/views.py` `otp_request`/`otp_verify`, mounted at
  `/auth/otp/`; on success fires the `AUTH_SECOND_FACTOR` filter (staff MFA),
  then `login()`.
- allauth is mounted at `/auth/`; `AUTHENTICATION_BACKENDS` =
  `ModelBackend` + allauth's `AuthenticationBackend`. No social provider
  configured yet. `user_logged_in` fires for *both* paths (customers/signals.py).

## Security — the critical design point (SSO must not bypass MFA)
allauth completes a social login by calling `login()` **directly**; it does
**not** pass through `core/auth/otp_verify`, so it never fires
`AUTH_SECOND_FACTOR`. **An SSO'd staff user would skip their TOTP second
factor.** The plugin MUST interpose the MFA gate on the SSO path. Approach:
- Subscribe to allauth's **`pre_social_login`** signal (fires after the IdP
  assertion is validated, before `login()`), and run the *same* decision the
  MFA hook runs: if `user.is_staff` and a confirmed `StaffMfaDevice` exists,
  stash pending state and redirect to `staff_mfa:challenge` (raise
  `ImmediateHttpResponse(redirect(...))` so allauth yields control). Reuse
  `staff_mfa.services.second_factor_response` — do **not** duplicate it
  (declare `staff_mfa` in `requires` when present, but degrade gracefully if
  MFA is disabled). This keeps **one** MFA decision point.
- A mandatory test asserts an enrolled-staff SSO login is forced through the
  TOTP challenge before the session is authenticated.

## JIT provisioning (`SocialAccountAdapter`)
A `StaffSsoAdapter(DefaultSocialAccountAdapter)` in the plugin overrides:
- `pre_social_login(request, sociallogin)` — match an existing `Customer` by
  verified email and link; enforce staff-gating (below); run the MFA gate.
- `populate_user(...)` — map IdP claims → `Customer` (`email`, `first_name`,
  `last_name`); stamp provenance in `Customer.metadata['sso']` (the model has a
  `metadata` JSONField; avoids touching `SOURCE_CHOICES`). Set `is_staff` per
  the gate.
Registered via `SOCIALACCOUNT_ADAPTER` — set by the plugin's `ready()` only
while enabled (so disabling restores allauth's default).

## Staff-gating  [CHOICE]
Restrict who may SSO in and who becomes staff:
- **(a) Email-domain allowlist** — `allowed_domains = ['acme.com']`; reject
  others. Simple, no IdP claim mapping. **Recommended default.**
- **(b) IdP group/role claim** — map `groups` claim → `is_staff` via
  `staff_groups = [...]`. More precise, needs the IdP to send groups.
Recommend shipping **(a)** + optional **(b)** when a `groups` claim is present;
a non-matching user is rejected (not silently admitted as a customer).

## Provider config  [CHOICE]
allauth stores providers in the `SocialApp` DB model **or** in
`SOCIALACCOUNT_PROVIDERS` settings. This repo configures nothing in settings
(DB-driven platform). Recommend a **dashboard settings panel**
(`contribute_settings_panel`, category `developer`) capturing OIDC
(`issuer`/discovery URL, `client_id`, `client_secret`, scopes) — secret stored
server-side, redacted from the assistant (mirror the MFA/ElevenLabs posture) —
and writing a `SocialApp` row (or settings provider) on save. Avoid making the
merchant use Django admin.

## Protocol order  [CHOICE]
- **OIDC first** (Okta/Entra/Google all speak it; simpler config: discovery
  URL + client id/secret), **then SAML** (metadata URL + entity_id + x509;
  allauth's `saml` provider). **Recommended:** ship OIDC in Phase 1–3, SAML as
  Phase 4. (Or do both at once if a target customer is SAML-only — flag it.)

## Surfaces
- **Login button:** add an SSO button to the staff sign-in page
  (`templates/account/login.html` and/or the `/auth/otp/` page) — contributed/
  overridden by the plugin, rendered only while enabled + configured.
- **Settings panel:** Settings → Developer → Staff SSO (IdP config + gating).
- **Audit:** `core.audit` `sso.*` events (login, JIT-create, gate-reject).

## Phases (each verifiable; OIDC path, mocked IdP in tests)
1. **Plugin scaffold + provider enable + settings panel** — register the OIDC
   provider from config; OFF by default. *Verify:* `makemigrations --check`
   clean; disable test (no provider, login = email-OTP).
2. **JIT adapter + staff-gating** — `StaffSsoAdapter`; first SSO login creates a
   staff `Customer`; domain/group gate. *Verify:* JIT-create test; gate-reject
   test (wrong domain → no account, no session).
3. **MFA gate on the SSO path (the security-critical bit)** — `pre_social_login`
   runs the staff_mfa decision. *Verify:* enrolled-staff SSO login is forced
   through TOTP before the session authenticates; with MFA disabled, SSO logs in
   directly.
4. **SAML provider + login-button UI polish + `sso.*` audit.** *Verify:* SAML
   metadata config round-trips; button renders only when enabled+configured.

## Tests (mandatory)
- **Permission/JIT:** first SSO assertion creates a linked staff `Customer`;
  a second login re-uses it (no duplicate).
- **Staff-gate:** disallowed domain/group → rejected (no `Customer`, no session).
- **SSO respects MFA:** enrolled staff via SSO must pass TOTP first (the
  no-bypass guarantee) — the headline security test.
- **Disable test:** plugin off → no provider, no button, login = email-OTP;
  `SOCIALACCOUNT_ADAPTER` reverts.
- **Contract:** exercise allauth's real adapter/signal interfaces (not mocks of
  our own code) — only the IdP transport is mocked.

## Risks / landmines
- **MFA bypass** (the one above) — Phase 3 is non-negotiable before SSO is
  enabled for an org that uses MFA.
- **Secret at rest** — client_secret stored server-side, never logged/assistant-
  exposed (matches the platform's existing secret posture).
- **Account-takeover via unverified email** — only link to an existing
  `Customer` on a *verified* IdP email; never auto-link on an unverified claim.
- **Lockout** — keep email-OTP available as the break-glass path for staff if
  the IdP is down (don't hard-disable OTP when SSO is on).
- **Migration** — likely none (allauth owns `SocialApp`/`SocialAccount`); if the
  plugin adds a config model, ship its migration (nullable adds only).

## Success criteria
- A staff user signs in through the org IdP; first login JIT-creates a linked,
  staff `Customer`; a disallowed user is rejected.
- An enrolled-staff SSO login is still forced through the MFA TOTP challenge.
- Customers and email-OTP are unaffected; disabling `staff_sso` removes the
  button + provider and login reverts to email-OTP exactly.
