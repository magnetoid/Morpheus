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

# plugins/installed/consent/tests/test_gating.py

Symbols in `plugins/installed/consent/tests/test_gating.py`.

- L37 `_cookie(**flags)` (function)
- L41 `_set_gdpr(on: bool)` (function) — Settings → General → GDPR features (the banner and the gate exist only
- L52 `_enable_meta_pixel()` (function)
- L62 `ContextProcessorTests` (class)
- L63 `setUp(self)` (method)
- L66 `_consent(self, **extra)` (method)
- L72 `test_no_decision_is_necessary_only_and_managed(self)` (method)
- L80 `test_a_decision_is_read_from_the_cookie(self)` (method)
- L86 `test_global_privacy_control_counts_as_a_refusal(self)` (method)
- L97 `test_an_explicit_choice_beats_the_gpc_signal(self)` (method)
- L102 `test_a_store_with_gdpr_features_off_is_unmanaged(self)` (method)
- L109 `BannerTests` (class)
- L110 `test_gpc_hides_the_banner(self)` (method)
- L118 `test_the_preferences_page_explains_gpc(self)` (method)
- L126 `TagGatingTests` (class)
- L127 `setUp(self)` (method)
- L133 `test_pixels_wait_for_marketing_consent(self)` (method)
- L144 `test_analytics_consent_alone_loads_only_the_beacon(self)` (method)
- L151 `test_an_unmanaged_store_keeps_its_tags(self)` (method)
- L158 `test_a_disabled_consent_app_keeps_the_tags(self)` (method)
- L167 `EveryMarketingBlockIsGatedTests` (class) — A static guard: a new pixel block that forgets the gate fails here.
- L170 `test_every_marketing_block_reads_consent(self)` (method)
