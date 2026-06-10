---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/ai_assistant/services/receipts.py

Symbols in `plugins/installed/ai_assistant/services/receipts.py`.

- L33 `_canonical_json(payload: Mapping[str, Any])` (function) — Stable JSON serialization suitable for HMAC signing.
- L48 `build_receipt_payload(intent)` (function) — Build the deterministic receipt envelope for an AgentIntent.
- L70 `sign_receipt(intent, secret: str)` (function) — Build and sign a receipt for `intent`. Returns (payload, signature).
- L80 `verify_receipt(payload: Mapping[str, Any], signature: str, secret: str)` (function) — Constant-time verification of an agent receipt.
