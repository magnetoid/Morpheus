---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/ai_assistant/services/receipts.py

Symbols in `plugins/installed/ai_assistant/services/receipts.py`.

- L35 `_canonical_json(payload: Mapping[str, Any])` (function) — Stable JSON serialization suitable for HMAC signing.
- L53 `build_receipt_payload(intent)` (function) — Build the deterministic receipt envelope for an AgentIntent.
- L75 `sign_receipt(intent, secret: str)` (function) — Build and sign a receipt for `intent`. Returns (payload, signature).
- L87 `verify_receipt(payload: Mapping[str, Any], signature: str, secret: str)` (function) — Constant-time verification of an agent receipt.
