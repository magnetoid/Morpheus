"""Subscription analytics — MRR, churn, trial funnel, plan breakdown.

Computed from this plugin's own Plan / Subscription / SubscriptionInvoice tables —
no new tables, no cross-plugin imports. The subscription plugins were feature-complete
but produced zero analytics; this module fills that.

Documented approximations:
- *Committed* MRR is a live snapshot (Σ active subs). Its history is NOT
  reconstructable (paused/past_due transitions aren't event-sourced), so the
  trend uses **recognized** MRR from PAID invoices instead.
- Trial conversion infers from `started_at + plan.trial_days` vs `cancelled_at`
  because per-sub state transitions aren't logged.
- Mixed-currency catalogs are summed as bare amounts under the first plan's
  currency (single-currency stores are the norm for subscriptions).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from djmoney.money import Money

# Normalize any billing interval to a per-month factor.
MONTHLY_FACTOR = {
    'day': Decimal(30),
    'week': Decimal(52) / Decimal(12),
    'month': Decimal(1),
    'year': Decimal(1) / Decimal(12),
}


def _monthly_amount(plan) -> Decimal:
    """A plan's normalized monthly value (price × interval factor ÷ interval_count)."""
    factor = MONTHLY_FACTOR.get(plan.interval, Decimal(1))
    count = Decimal(plan.interval_count or 1)
    return (plan.price.amount * factor) / count


def _money(amount: Decimal, ccy: str = 'USD') -> Money:
    return Money(amount.quantize(Decimal('0.01')), ccy)


def committed_mrr() -> Money:
    """Live monthly recurring revenue committed by every ACTIVE subscription."""
    from plugins.installed.subscriptions.models import Subscription

    total = Decimal(0)
    ccy = 'USD'
    for sub in Subscription.objects.filter(state='active').select_related('plan'):
        total += _monthly_amount(sub.plan)
        ccy = str(sub.plan.price.currency)
    return _money(total, ccy)


def mrr_trend(months: int = 12) -> list[dict]:
    """Recognized MRR per calendar month from PAID invoices (period-length-normalized)."""
    from plugins.installed.subscriptions.models import SubscriptionInvoice

    start = timezone.now() - timedelta(days=months * 31)
    monthly: dict = defaultdict(Decimal)
    for inv in SubscriptionInvoice.objects.filter(state='paid', period_start__gte=start):
        days = max(1, (inv.period_end - inv.period_start).days)
        monthly[(inv.period_start.year, inv.period_start.month)] += (
            inv.amount.amount * Decimal(30) / Decimal(days)
        )
    return [
        {'year': y, 'month': m, 'mrr': amt.quantize(Decimal('0.01'))}
        for (y, m), amt in sorted(monthly.items())
    ]


def churn_rate(days: int = 30) -> dict:
    """Subscriptions cancelled in the window ÷ those active at the window's start."""
    from plugins.installed.subscriptions.models import Subscription

    now = timezone.now()
    window_start = now - timedelta(days=days)
    active_at_start = (
        Subscription.objects.filter(started_at__lt=window_start)
        .exclude(cancelled_at__lt=window_start)
        .count()
    )
    cancelled = Subscription.objects.filter(
        cancelled_at__gte=window_start, cancelled_at__lte=now
    ).count()
    return {
        'cancelled': cancelled,
        'active_at_start': active_at_start,
        'rate': round(cancelled / active_at_start * 100, 1) if active_at_start else None,
    }


def trial_funnel(days: int = 90) -> dict:
    """Trials started / converted / cancelled-in-trial over the window."""
    from plugins.installed.subscriptions.models import Subscription

    now = timezone.now()
    start = now - timedelta(days=days)
    started = converted = cancelled_in_trial = 0
    for sub in Subscription.objects.filter(
        started_at__gte=start, plan__trial_days__gt=0
    ).select_related('plan'):
        started += 1
        trial_end = sub.started_at + timedelta(days=sub.plan.trial_days)
        if sub.cancelled_at and sub.cancelled_at < trial_end:
            cancelled_in_trial += 1
        elif now >= trial_end and sub.state in ('active', 'past_due', 'paused'):
            converted += 1
    return {
        'started': started,
        'converted': converted,
        'cancelled_in_trial': cancelled_in_trial,
        'conversion_rate': round(converted / started * 100, 1) if started else None,
    }


def plan_breakdown() -> list[dict]:
    """Per-plan active count, committed MRR, trialing, and 30-day cancels."""
    from plugins.installed.subscriptions.models import Plan

    since = timezone.now() - timedelta(days=30)
    out = []
    for plan in Plan.objects.all():
        active = plan.subscriptions.filter(state='active').count()
        out.append(
            {
                'plan': plan.name,
                'price': plan.price,
                'interval': plan.interval,
                'active': active,
                'trialing': plan.subscriptions.filter(state='trialing').count(),
                'cancelled_30d': plan.subscriptions.filter(cancelled_at__gte=since).count(),
                'mrr': _money(_monthly_amount(plan) * active, str(plan.price.currency)),
            }
        )
    out.sort(key=lambda r: r['mrr'].amount, reverse=True)
    return out
