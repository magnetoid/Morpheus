---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/orders/refunds.py

Symbols in `plugins/installed/orders/refunds.py`.

- L33 `ReturnRequest` (class) — Customer- or staff-initiated return.
- L108 `__str__(self)` (method)
- L111 `save(self, *args, **kwargs)` (method)
- L118 `RefundService` (class) — Process refunds against the underlying payment provider.
- L123 `process(cls, *, order, amount: Money, reason: str='customer_request', notes: str='', actor=None)` (method) — Create a Refund row and call the provider. Idempotent on
- L173 `_provider_refund(*, order, amount: Money, refund)` (method) — Best-effort: call Stripe if a charge exists; otherwise success-with-log.
- L215 `ReturnService` (class) — Lifecycle of a `ReturnRequest`.
- L219 `create_request(cls, *, order, items: list[dict], reason: str='other', customer_note: str='', requested_by=None)` (method)
- L253 `approve(cls, rr: ReturnRequest, *, decided_by=None, refund_amount: Money | None=None)` (method)
- L268 `reject(cls, rr: ReturnRequest, *, decided_by=None, staff_note: str='')` (method)
- L280 `mark_received_and_refund(cls, rr: ReturnRequest, *, actor=None, as_store_credit: bool=False)` (method) — Close out a return.
- L346 `_compute_refund(rr: ReturnRequest)` (method)
