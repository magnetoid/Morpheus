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

# themes/test_head_contract.py

Symbols in `themes/test_head_contract.py`.

- L40 `HeadContractTests` (class) — Runs only when the active theme declares `head_contract >= 1`.
- L44 `setUpTestData(cls)` (method)
- L68 `setUp(self)` (method)
- L75 `_paths(self)` (method)
- L88 `test_each_page_emits_exactly_one_of_each_head_element(self)` (method)
- L99 `test_private_pages_are_noindex_and_public_pages_are_not(self)` (method)
- L110 `test_the_theme_does_not_hardcode_the_brand_in_the_head(self)` (method) — The brand belongs in settings, not in markup.
- L131 `test_head_survives_the_seo_app_being_disabled(self)` (method) — Disable litmus test, applied to the head.
- L155 `EveryContractThemeTests` (class) — The contract must be checked for EVERY theme that signs it.
- L174 `_is_amp(path)` (method) — AMP pages are exempt: the spec REQUIRES each to carry its own
- L179 `test_no_contract_theme_hardcodes_a_tag_the_head_document_owns(self)` (method)
- L224 `_activate_theme(testcase, name: str)` (function) — Render with theme `name` active; the previous VALUE is restored on cleanup.
- L243 `_contract_themes()` (function) — Every theme that signs the head contract and can run in this process.
- L255 `ErrorHeadEveryThemeTests` (class) — A 404 names no URL and describes no entity — under EVERY contract theme.
- L266 `test_a_missing_page_carries_a_bare_head_under_every_theme(self)` (method)
- L285 `ThemeMarkupContractTests` (class) — What a contract theme's templates may not contain at all.
- L300 `test_contract_themes_and_storefront_plugin_templates_emit_none(self)` (method)
- L336 `DeadBlockTests` (class) — No template overrides a block that nothing above it renders.
- L347 `_dead_blocks(name: str)` (method)
- L368 `_scan(self, root, offenders, label)` (method)
- L381 `test_no_template_overrides_a_block_its_base_never_renders(self)` (method)
