---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/b2b/services.py

Symbols in `plugins/installed/b2b/services.py`.

- L19 `resolve_price_for_account(*, product, account=None, variant=None)` (function) — Find the best price-list price for this product+account, else fall back.
- L40 `create_quote(*, account, contact, owner, lines: Iterable[dict], valid_until=None, note: str='')` (function) — Create a Quote with line items at fixed prices.
- L81 `send_quote(quote)` (function)
- L87 `accept_quote(quote)` (function)
