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

# plugins/installed/orders/refunds.py

Symbols in `plugins/installed/orders/refunds.py`.

- L33 `ReturnRequest` (class) — Customer- or staff-initiated return.
- L108 `__str__(self)` (method)
- L111 `save(self, *args, **kwargs)` (method)
- L118 `RefundService` (class) — Process refunds against the underlying payment provider.
- L123 `process(cls, *, order, amount: Money, reason: str='customer_request', notes: str='', actor=None)` (method) — Create a Refund row and call the provider. Idempotent on
- L210 `record_external(cls, *, order, reason: str='other', notes: str='', actor=None)` (method) — Record a refund already made outside Morpheus (in the gateway's own
- L248 `ReturnService` (class) — Lifecycle of a `ReturnRequest`.
- L252 `create_request(cls, *, order, items: list[dict], reason: str='other', customer_note: str='', requested_by=None)` (method)
- L286 `approve(cls, rr: ReturnRequest, *, decided_by=None, refund_amount: Money | None=None)` (method)
- L301 `reject(cls, rr: ReturnRequest, *, decided_by=None, staff_note: str='')` (method)
- L313 `mark_received_and_refund(cls, rr: ReturnRequest, *, actor=None, as_store_credit: bool=False)` (method) — Close out a return.
- L379 `_compute_refund(rr: ReturnRequest)` (method)
