---
type: progress
status: active
tags:
- active
links: []
created: '2026-07-01T04:29:08'
updated: '2026-07-01T04:29:08'
---

# Progress

v0.2.18 SHIPPED + prod-verified on dotbooks.store (clean: ~90s recreate 502/503 window 04:24-04:25 then 200; home 200, dashboard 302). Commits 49e1138/864ecc8/b8fc602 pushed to magnetoid/morpheus main.
Root fix for 'disabled book_product but its Book details card kept showing': (1) core/hooks.py fire()/filter() now SKIP any handler owned by an inactive plugin — ownership tagged via Plugin.register_hook(plugin=self.name), predicate wired via hook_registry.set_active_check(registry.is_active), no core->plugins import; makes EVERY register_hook contribution disable-safe. (2) book_product's Book details product-form card migrated from hard-coded admin_dashboard template/import to PRODUCT_FORM_CARDS/PRODUCT_FORM_SAVED hooks. Root-cause: deactivate() intentionally does NOT unwind ready()-wired hooks. Verified: core/tests/test_hook_disable_gating.py (6) + test_disable_guards (8) green, 14 tests OK.
Enforcement/docs: ADR 0024 recorded (2 drift rules: keep the bus gating; render optional-plugin surfaces via hooks not hard imports). ADR 0006 amended (it had prescribed the try/except anti-pattern). ADR 0006/0021 got machine-readable drift guards (b8fc602). CLAUDE.md landmine added. check_drift(new_only)=No drift.
'Merge all branches' request was a no-op: the 8 Dependabot branches were already deleted on the remote (stale local refs, cleared by fetch --prune); only main exists.
