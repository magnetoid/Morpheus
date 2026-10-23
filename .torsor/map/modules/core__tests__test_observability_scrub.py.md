---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/tests/test_observability_scrub.py

Symbols in `core/tests/test_observability_scrub.py`.

- L17 `_FakeSpan` (class) — Stand-in for a ReadableSpan — only the backing `_attributes` map matters.
- L20 `__init__(self, attributes)` (method)
- L24 `ScrubSpanAttributesTests` (class)
- L25 `test_pii_attributes_redacted_in_place(self)` (method)
- L49 `test_none_attributes_returns_zero_and_does_not_raise(self)` (method)
- L52 `test_missing_attributes_returns_zero_and_does_not_raise(self)` (method)
- L58 `test_empty_attributes_returns_zero(self)` (method)
- L61 `test_idempotent_no_double_redaction(self)` (method)
