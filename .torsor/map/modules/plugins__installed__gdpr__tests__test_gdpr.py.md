---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/gdpr/tests/test_gdpr.py

Symbols in `plugins/installed/gdpr/tests/test_gdpr.py`.

- L32 `_customer(email='dsr@example.com')` (function)
- L36 `DataExportTests` (class)
- L37 `test_export_streams_zip_with_customer_data(self)` (method)
- L54 `test_export_get_requires_login(self)` (method)
- L60 `ErasureTests` (class)
- L61 `test_erasure_anonymises_via_customers_service(self)` (method)
- L75 `test_erasure_rejects_wrong_email(self)` (method)
- L85 `GateTests` (class) — The gdpr_required() master-switch gate (moved here from storefront).
- L88 `setUp(self)` (method)
- L91 `_set_gdpr(self, on: bool)` (method)
- L97 `test_gate_default_passes(self)` (method)
- L100 `test_gate_raises_when_disabled(self)` (method)
- L105 `test_privacy_hub_404s_when_disabled(self)` (method)
- L113 `DisableTests` (class) — Every surface the plugin contributes must vanish when it is disabled.
- L116 `_gdpr_blocks(self, slot)` (method)
- L119 `test_surfaces_present_while_active(self)` (method)
- L124 `test_surfaces_vanish_on_disable(self)` (method)
- L132 `LegalPageSeedTests` (class)
- L139 `test_seed_is_idempotent(self)` (method)
- L156 `test_management_command_runs(self)` (method)
- L162 `test_post_migrate_handler_self_heals_missing_pages(self)` (method) — A swallowed first seed (0002 marked applied, zero pages, footer 404s)
- L178 `DeadCodeLitmusTests` (class) — Removing the old dead storefront views left no dangling reference.
- L181 `test_storefront_account_has_no_gdpr_view_orphans(self)` (method)
