---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/orders/refunds.py

Symbols in `plugins/installed/orders/refunds.py`.

- L33 `ReturnRequest` (class) — Customer- or staff-initiated return.
- L93 `__str__(self)` (method)
- L96 `save(self, *args, **kwargs)` (method)
- L103 `RefundService` (class) — Process refunds against the underlying payment provider.
- L108 `process(cls, *, order, amount: Money, reason: str='customer_request', notes: str='', actor=None)` (method) — Create a Refund row and call the provider. Idempotent on
- L148 `_provider_refund(*, order, amount: Money, refund)` (method) — Best-effort: call Stripe if a charge exists; otherwise success-with-log.
- L181 `ReturnService` (class) — Lifecycle of a `ReturnRequest`.
- L185 `create_request(cls, *, order, items: list[dict], reason: str='other', customer_note: str='', requested_by=None)` (method)
- L210 `approve(cls, rr: ReturnRequest, *, decided_by=None, refund_amount: Money | None=None)` (method)
- L223 `reject(cls, rr: ReturnRequest, *, decided_by=None, staff_note: str='')` (method)
- L235 `mark_received_and_refund(cls, rr: ReturnRequest, *, actor=None, as_store_credit: bool=False)` (method) — Close out a return.
- L298 `_compute_refund(rr: ReturnRequest)` (method)
