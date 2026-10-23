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

# plugins/installed/staff_sso/tests/test_saml.py

Symbols in `plugins/installed/staff_sso/tests/test_saml.py`.

- L37 `_request()` (function)
- L48 `_saml_sociallogin(email, *, verified=False, groups=None, uid='saml-nameid-1', user=None)` (function) — Build a SAML SocialLogin the way allauth's ACS view does: account.provider
- L66 `_configure(*, domains='acme.com', groups='', enabled=True, mfa=True, saml_enabled=True)` (function) — Write plugin config (SAML section populated) + sync the SAML SocialApp +
- L106 `SamlJitProvisioning` (class) — (1) First SAML login JIT-creates a staff Customer; a second re-uses it.
- L109 `setUp(self)` (method)
- L113 `test_first_login_populates_staff_customer(self)` (method)
- L127 `test_existing_customer_is_linked_not_duplicated(self)` (method)
- L137 `SamlStaffGate` (class) — (2) The staff gate rejects a disallowed domain / group on the SAML path —
- L141 `setUp(self)` (method)
- L144 `test_disallowed_domain_rejected_no_account_no_session(self)` (method)
- L152 `test_disallowed_group_rejected(self)` (method)
- L161 `test_matching_saml_group_admitted_off_domain(self)` (method)
- L170 `SamlRespectsMfa` (class) — (3) THE HEADLINE: an enrolled-staff SAML login is forced through the TOTP
- L175 `setUp(self)` (method)
- L186 `test_enrolled_staff_forced_to_totp_challenge(self)` (method)
- L195 `test_with_mfa_disabled_no_challenge(self)` (method)
- L201 `SamlEmailTrust` (class) — SAML accepts the signed-assertion email even without a per-address
- L206 `setUp(self)` (method)
- L210 `test_unverified_flag_still_links_existing(self)` (method)
- L220 `test_no_email_rejected(self)` (method)
- L228 `SamlSyncAndConfig` (class) — SocialApp sync round-trips the allauth SAML settings shape, and disabling
- L232 `test_metadata_url_settings_shape(self)` (method)
- L251 `test_attribute_mapping_merges_onto_allauth_default(self)` (method) — REGRESSION (BLOCKER): configuring ONLY groups_attr must NOT wipe
- L286 `test_assertions_must_be_signed(self)` (method) — Staff boundary hardening: the synced SocialApp requires signed SAML
- L298 `test_explicit_idp_settings_shape(self)` (method)
- L320 `test_is_saml_configured(self)` (method)
- L337 `test_configured_then_disabled_removes_app(self)` (method)
