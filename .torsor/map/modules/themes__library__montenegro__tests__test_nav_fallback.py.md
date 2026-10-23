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

# themes/library/montenegro/tests/test_nav_fallback.py

Symbols in `themes/library/montenegro/tests/test_nav_fallback.py`.

- L15 `MontenegroNavFallbackTests` (class)
- L16 `_render(self, extra: dict)` (method)
- L22 `test_the_header_renders_with_no_nav_context_at_all(self)` (method) — The exact production shape: none of the nav keys exist.
- L27 `test_the_header_renders_with_the_legacy_keys_only(self)` (method) — A store whose nav comes from the legacy keys still gets a menu.
- L42 `test_the_header_renders_with_the_namespaced_payload_only(self)` (method) — The booking plugin's own shape, without the legacy aliases.
- L64 `NavContextProcessorRegistrationTests` (class)
- L65 `test_the_booking_plugin_registers_its_storefront_nav_processor(self)` (method) — Written-but-unregistered was the actual bug: the module existed and
