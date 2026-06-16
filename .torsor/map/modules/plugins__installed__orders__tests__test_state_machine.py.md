---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/orders/tests/test_state_machine.py

Symbols in `plugins/installed/orders/tests/test_state_machine.py`.

- L20 `_order()` (function)
- L28 `HappyPathTests` (class)
- L29 `test_full_lifecycle(self)` (method)
- L61 `test_ship_straight_from_processing(self)` (method)
- L69 `test_fulfill_from_partially_fulfilled(self)` (method)
- L79 `IllegalTransitionTests` (class)
- L80 `test_cannot_skip_confirm(self)` (method)
- L85 `test_cannot_ship_a_pending_order(self)` (method)
- L90 `test_cannot_deliver_before_shipping(self)` (method)
- L96 `test_cannot_confirm_twice(self)` (method)
- L102 `test_direct_status_assignment_is_blocked(self)` (method)
- L108 `CancelTests` (class)
- L109 `test_cancel_from_pending(self)` (method)
- L120 `test_cancel_from_shipped(self)` (method)
- L128 `test_transitions_blocked_after_cancel(self)` (method)
