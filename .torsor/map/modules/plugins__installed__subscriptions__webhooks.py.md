---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/subscriptions/webhooks.py

Symbols in `plugins/installed/subscriptions/webhooks.py`.

- L46 `handle_stripe_event(event_type=None, payload=None, **_kwargs)` (function) — Reconcile one Stripe webhook event onto the local subscription rows.
- L76 `_handle_invoice_paid(inv)` (function) — A billing cycle was paid: upsert a paid invoice + advance the period.
- L122 `_handle_invoice_failed(inv)` (function) — A charge failed: open the invoice, go ``past_due``, arm dunning.
- L158 `_handle_subscription_updated(obj)` (function) — Mirror a ``customer.subscription.updated``: status + period + cancel flag.
- L193 `_handle_subscription_deleted(obj)` (function) — A subscription ended: ``cancelled`` (or ``expired``).
- L208 `_event_object(event)` (function) — The ``data.object`` sub-dict of a Stripe event payload (``None`` if absent).
- L214 `_subscription_for(provider_subscription_id)` (function) — The local ``Subscription`` for a Stripe subscription id (``None`` if unknown).
- L224 `_existing_invoice(sub, invoice_id)` (function) — A local invoice row already recorded for this Stripe invoice id (or ``None``).
- L231 `_invoice_period(inv)` (function) — ``(period_start, period_end)`` for the subscription's next cycle.
- L249 `_minor_to_money(minor, currency)` (function) — Stripe minor units + currency → a :class:`Money` (fail-soft on payments absent).
- L276 `_enter_past_due(sub, now)` (function) — Set ``past_due`` and arm dunning, persisting the row.
- L283 `_arm_dunning(sub, now)` (function) — Stamp the dunning anchor (once) into ``metadata`` without saving.
- L295 `_clear_dunning(sub)` (function) — Drop the dunning marker from ``metadata`` without saving.
