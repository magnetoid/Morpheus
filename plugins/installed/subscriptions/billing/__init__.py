"""Stripe Billing adapter for the subscriptions plugin.

Fills the "Stripe Billing adapter slot" declared in ``app.py``. The adapter
is a thin, fail-soft wrapper over the ``stripe`` SDK that reuses the payments
plugin's Stripe customer vault + key accessor (service-layer coupling, lazy
imports — ``payments`` is an *optional* dependency, so a manual-only merchant
running without it degrades gracefully instead of crashing).
"""

from __future__ import annotations

from plugins.installed.subscriptions.billing.stripe_adapter import StripeSubscriptionAdapter

__all__ = ['StripeSubscriptionAdapter']
