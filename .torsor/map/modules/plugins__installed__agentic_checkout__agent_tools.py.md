---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/agentic_checkout/agent_tools.py

Symbols in `plugins/installed/agentic_checkout/agent_tools.py`.

- L33 `_resolve(session_id: Any)` (function) — Resolve a session id to its cart via the ACP resolver (IDOR + TTL guard).
- L52 `cart_create_tool()` (function)
- L81 `cart_add_item_tool(*, session_id: str, id: str='', product_id: str='', variant_id: str='', quantity: int=1)` (function)
- L108 `cart_get_tool(*, session_id: str)` (function)
- L123 `checkout_get_session_tool(*, session_id: str)` (function)
- L153 `checkout_set_buyer_tool(*, session_id: str, email: str='', shipping_address: dict | None=None)` (function)
