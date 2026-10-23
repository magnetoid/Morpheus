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

# core/observability.py

Symbols in `core/observability.py`.

- L27 `_hash_token(match: re.Match)` (function)
- L32 `scrub_pii(text: str)` (function) — Replace email/phone/IPv4 occurrences in ``text`` with stable hashes.
- L43 `scrub_span_attributes(span)` (function) — Redact PII in a span's string attributes IN PLACE. Returns the count
- L71 `init_observability()` (function)
