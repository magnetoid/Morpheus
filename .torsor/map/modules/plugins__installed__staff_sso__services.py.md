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

# plugins/installed/staff_sso/services.py

Symbols in `plugins/installed/staff_sso/services.py`.

- L41 `_csv_list(value)` (function) — Normalise a CSV string OR a list into a lowercased, de-blanked list.
- L52 `get_settings(plugin)` (function) — Read the saved IdP config off the plugin's PluginConfig row.
- L64 `is_configured(cfg: dict)` (function) — An IdP is usable only when issuer + client id + secret are all present.
- L71 `gate_decision(cfg: dict, *, email: str, groups: list[str])` (function) — Return True iff this identity may sign in as staff.
- L91 `claim_groups(data)` (function) — Pull a groups/roles claim out of the IdP assertion (best-effort).
- L105 `sync_social_app(cfg: dict)` (function) — Create/update the single OIDC SocialApp from saved config, or remove it
- L144 `get_saml_settings(plugin)` (function) — Read the saved SAML IdP config off the plugin's PluginConfig row.
- L171 `is_saml_configured(cfg: dict)` (function) — A SAML IdP is usable when SAML is enabled AND the IdP is described either
- L182 `build_saml_app_settings(cfg: dict)` (function) — Translate our flat config into the nested dict allauth's saml provider
- L232 `sync_saml_app(cfg: dict)` (function) — Create/update the single SAML SocialApp from saved config, or remove it
- L268 `audit(event_type: str, *, actor=None, target: str='', metadata=None, severity='info')` (function) — Record an sso.* audit event. Never raises (core.audit swallows DB errors).
