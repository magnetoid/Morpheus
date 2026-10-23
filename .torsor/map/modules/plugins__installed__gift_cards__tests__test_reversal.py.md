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

# plugins/installed/gift_cards/tests/test_reversal.py

Symbols in `plugins/installed/gift_cards/tests/test_reversal.py`.

- L23 `_usd(n)` (function)
- L27 `ReverseRedemptionServiceTests` (class)
- L28 `_issue_and_redeem(self, reference='ORD-123')` (method) — Issue a $50 card, spend $10 against ``reference`` → balance $40.
- L36 `test_reversal_recredits_balance_and_writes_refund_row(self)` (method)
- L50 `test_reversal_is_idempotent(self)` (method)
- L66 `test_no_redeem_rows_is_noop(self)` (method)
- L72 `ReverseRedemptionHookTests` (class)
- L73 `test_order_cancelled_hook_recredits_card(self)` (method)
