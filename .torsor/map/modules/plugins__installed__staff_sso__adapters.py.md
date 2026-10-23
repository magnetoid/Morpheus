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

# plugins/installed/staff_sso/adapters.py

Symbols in `plugins/installed/staff_sso/adapters.py`.

- L27 `_get_plugin()` (function) — Resolve the live staff_sso plugin instance, or None when not active.
- L36 `_provider_id(sociallogin)` (function)
- L40 `_is_saml(sociallogin)` (function)
- L44 `_verified_email(sociallogin)` (function) — The authoritative IdP-asserted email, lowercased — or '' when none.
- L71 `_claims(sociallogin)` (function)
- L76 `_resolve_groups(sociallogin, cfg)` (function) — Pull the group/role claim out of the assertion for the staff gate.
- L101 `_user_in_db(user)` (function) — True iff ``user`` is a saved row. Customer.id defaults to uuid4 at
- L110 `_deny(request, message: str)` (function) — Render an access-denied page and raise it so allauth aborts the login —
- L122 `_gate_config(plugin, sociallogin)` (function) — Resolve the gate/provenance config for whichever of our providers this
- L132 `StaffSsoAdapter` (class) — The process-wide ``SOCIALACCOUNT_ADAPTER`` while staff_sso is enabled.
- L141 `pre_social_login(self, request, sociallogin)` (method) — Run after the IdP assertion validates, before allauth's ``login()``.
- L204 `_link_existing(self, request, sociallogin, email)` (method) — If a Customer already exists for this verified email, connect the
- L235 `_mfa_gate(request, user)` (method) — Delegate to staff_mfa's single decision point, if it's active.
- L249 `populate_user(self, request, sociallogin, data)` (method) — Map IdP claims → Customer on a JIT-create, stamp SSO provenance, and
