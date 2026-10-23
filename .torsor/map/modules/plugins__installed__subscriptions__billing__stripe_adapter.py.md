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

# plugins/installed/subscriptions/billing/stripe_adapter.py

Symbols in `plugins/installed/subscriptions/billing/stripe_adapter.py`.

- L47 `_map_state(stripe_status: str, default: str='active')` (function) — Map a Stripe subscription status to a local state (``default`` if new).
- L52 `_stripe_key()` (function) — Stripe secret key via the payments plugin's accessor.
- L66 `_get(obj, key)` (function) — Read ``key`` off a Stripe object dict-safely.
- L78 `_ts_to_dt(ts)` (function) — Unix seconds → aware UTC datetime (``None`` / ``0`` passes through).
- L85 `_period(stripe_sub)` (function) — ``(current_period_start, current_period_end)`` as aware datetimes.
- L103 `StripeSubscriptionAdapter` (class) — Stripe Billing operations for ``Plan(provider='stripe')`` and its subs.
- L113 `sync_plan(cls, plan)` (method) — Ensure a Stripe Product+Price for ``plan``; return its price id.
- L157 `payment_method_from_setup_intent(cls, setup_intent_id: str, customer)` (method) — The payment method a *succeeded* SetupIntent collected for ``customer``.
- L200 `start_subscription(cls, subscription, payment_method_id: str)` (method) — Create the Stripe subscription for ``subscription`` and charge it.
- L272 `cancel_subscription(cls, subscription, *, at_period_end: bool=True)` (method) — Cancel the Stripe subscription and mirror the flag locally.
- L314 `pause_subscription(cls, subscription)` (method) — Pause billing on the Stripe subscription (``pause_collection``) and
- L320 `resume_subscription(cls, subscription)` (method) — Clear the Stripe pause and mirror ``state='active'`` locally. Fail soft.
- L325 `_set_pause(cls, subscription, *, paused: bool)` (method)
