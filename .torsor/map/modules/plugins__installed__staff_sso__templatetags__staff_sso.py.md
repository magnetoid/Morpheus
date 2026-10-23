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

# plugins/installed/staff_sso/templatetags/staff_sso.py

Symbols in `plugins/installed/staff_sso/templatetags/staff_sso.py`.

- L30 `_is_configured()` (function) — True iff an OIDC SocialApp for our provider exists with a client_id —
- L51 `_plugin_active()` (function) — Enabled-gate shared by both protocol tags.
- L61 `_saml_app()` (function) — Return the synced SAML SocialApp (or None) — the live source of truth the
- L83 `staff_sso_login_url(context)` (function) — Return the allauth OIDC provider login URL, or '' when off/unconfigured.
- L111 `staff_sso_saml_login_url(context)` (function) — Return the allauth SAML provider login URL, or '' when off/unconfigured.
