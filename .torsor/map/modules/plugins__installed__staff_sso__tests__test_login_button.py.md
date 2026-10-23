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

# plugins/installed/staff_sso/tests/test_login_button.py

Symbols in `plugins/installed/staff_sso/tests/test_login_button.py`.

- L26 `_request()` (function)
- L39 `_configure(*, domains='acme.com', enabled=True)` (function) — Write the plugin config + sync the SocialApp + drive registry state,
- L68 `_render_tag(request)` (function) — Render the tag in isolation and return the captured URL string.
- L74 `_render_block(request, extra=None)` (function) — Render the actual block template the StorefrontBlock points at.
- L84 `ConfiguredButtonRenders` (class) — Enabled + a configured SocialApp → the tag returns a URL and the block
- L88 `setUp(self)` (method)
- L91 `test_tag_returns_login_url(self)` (method)
- L97 `test_block_renders_sso_link(self)` (method)
- L104 `test_block_respects_next_param(self)` (method)
- L109 `UnconfiguredRendersNothing` (class) — No SocialApp / blank config → the tag is falsy and the block draws no
- L113 `test_no_socialapp_tag_is_empty(self)` (method)
- L119 `test_no_socialapp_block_is_empty(self)` (method)
- L127 `DisabledRendersNothing` (class) — Plugin disabled → even with a SocialApp present, no button renders.
- L130 `test_disabled_plugin_tag_is_empty(self)` (method)
- L136 `test_disabled_plugin_block_is_empty(self)` (method)
- L144 `_configure_saml(*, enabled=True, saml_enabled=True)` (function) — Write config with the SAML section populated + sync the SAML SocialApp +
- L175 `_render_saml_tag(request)` (function)
- L180 `SamlButtonRenders` (class) — SAML enabled + configured → the SAML tag returns a URL and the block
- L184 `setUp(self)` (method)
- L187 `test_saml_tag_returns_login_url(self)` (method)
- L194 `test_block_renders_saml_link(self)` (method)
- L200 `SamlButtonDisableSafe` (class) — (4) disable-safe — SAML disabled / plugin disabled → no SAML SocialApp,
- L204 `test_saml_disabled_no_app_no_button(self)` (method)
- L213 `test_plugin_disabled_no_saml_button(self)` (method)
