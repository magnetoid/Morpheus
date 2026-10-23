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

# plugins/installed/staff_sso/tests/test_adapter.py

Symbols in `plugins/installed/staff_sso/tests/test_adapter.py`.

- L31 `_request()` (function)
- L44 `_sociallogin(email, *, verified=True, claims=None, uid='idp-sub-1', user=None)` (function) — Build a SocialLogin the way allauth does mid-flow: a not-yet-saved user,
- L58 `_configure(*, domains='acme.com', groups='', enabled=True, mfa=True)` (function) — Write the plugin config + force registry active-state for the test.
- L96 `JitProvisioning` (class) — First SSO login creates a linked staff Customer; a second re-uses it.
- L99 `setUp(self)` (method)
- L103 `test_first_login_populates_staff_customer(self)` (method)
- L116 `test_existing_customer_is_linked_not_duplicated(self)` (method)
- L126 `test_existing_non_staff_customer_is_promoted(self)` (method)
- L144 `StaffGate` (class)
- L145 `setUp(self)` (method)
- L148 `test_disallowed_domain_rejected_no_account_no_session(self)` (method)
- L156 `test_disallowed_group_rejected(self)` (method)
- L164 `test_matching_group_admitted_off_domain(self)` (method)
- L171 `SsoRespectsMfa` (class) — The headline: an enrolled-staff SSO login is forced through TOTP, and
- L175 `setUp(self)` (method)
- L186 `test_enrolled_staff_forced_to_totp_challenge(self)` (method)
- L196 `test_with_mfa_disabled_no_challenge(self)` (method)
- L203 `UnverifiedEmailGuard` (class) — Account-takeover guard: an unverified IdP email is never auto-linked
- L207 `setUp(self)` (method)
- L211 `test_unverified_email_not_linked(self)` (method)
- L226 `DisableSafe` (class) — Blank config → no provider registered; SSO inert (email-OTP unaffected).
- L229 `test_blank_config_registers_no_socialapp(self)` (method)
- L239 `test_configured_then_blank_removes_socialapp(self)` (method)
- L256 `GateUnit` (class) — Pure gate_decision() truth table — fail-closed when nothing configured.
- L259 `test_empty_config_fails_closed(self)` (method)
- L266 `test_domain_match(self)` (method)
- L271 `test_group_match(self)` (method)
