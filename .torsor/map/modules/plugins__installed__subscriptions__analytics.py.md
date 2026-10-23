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

# plugins/installed/subscriptions/analytics.py

Symbols in `plugins/installed/subscriptions/analytics.py`.

- L35 `_monthly_amount(plan)` (function) — A plan's normalized monthly value (price × interval factor ÷ interval_count).
- L42 `_money(amount: Decimal, ccy: str='USD')` (function)
- L46 `committed_mrr()` (function) — Live monthly recurring revenue committed by every ACTIVE subscription.
- L58 `mrr_trend(months: int=12)` (function) — Recognized MRR per calendar month from PAID invoices (period-length-normalized).
- L75 `churn_rate(days: int=30)` (function) — Subscriptions cancelled in the window ÷ those active at the window's start.
- L96 `trial_funnel(days: int=90)` (function) — Trials started / converted / cancelled-in-trial over the window.
- L120 `plan_breakdown()` (function) — Per-plan active count, committed MRR, trialing, and 30-day cancels.
