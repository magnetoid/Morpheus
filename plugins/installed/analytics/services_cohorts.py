"""Cohort retention computation.

A cohort is the set of customers who first appeared in a given week.
Retention[N] = % of that cohort who placed an order in week N after.

For an e-commerce shop, this is the single most important metric
besides revenue — it tells you whether each marketing dollar is
buying recurring revenue or just one-time transactions. Without
cohort retention you cannot reliably tell whether changes you ship
are growing LTV or just churning customers.

The math:
  - Cohort week: ISO week of customer.created_at.
  - Period N: ISO weeks since cohort week.
  - Retention: percent of cohort members who placed at least one
    order in period N (or had any analytics event, depending on the
    metric).

Three metrics are computed in one pass:
  - retention_order — % who placed an order
  - retention_active — % who had any AnalyticsEvent (broader, includes
    pageviews; less stringent than orders but catches engaged-but-not-
    yet-purchased customers).
  - retention_revenue — sum of order totals per cohort × period
    (for cumulative LTV-by-cohort views).

Cap at 12 periods (weeks) by default. For shops with longer LTVs we
can extend; for 99% of cases week 12 retention is the leading
indicator.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils import timezone

logger = logging.getLogger('morpheus.analytics.cohorts')

DEFAULT_PERIOD_COUNT = 12
DEFAULT_COHORT_COUNT = 8  # last 8 weekly cohorts


@dataclass(slots=True)
class CohortCell:
    """One (cohort_week, period_n) intersection."""

    customers: int = 0
    retention_pct: float = 0.0
    order_customers: int = 0
    order_retention_pct: float = 0.0
    revenue: Decimal = field(default_factory=lambda: Decimal('0'))


@dataclass(slots=True)
class CohortRow:
    """One cohort across its periods."""

    week_start: date
    week_label: str
    size: int  # original cohort size
    cells: list[CohortCell]


def compute_cohorts(
    *,
    cohort_count: int = DEFAULT_COHORT_COUNT,
    period_count: int = DEFAULT_PERIOD_COUNT,
    metric: str = 'order',
) -> dict:
    """Return cohort table data for the dashboard.

    Returns:
        {
            'metric': 'order' | 'active' | 'revenue',
            'periods': [0..N-1],  # week labels
            'rows': [CohortRow, ...],
            'totals': {'customers': int, 'cohorts': int},
        }
    """
    if metric not in ('order', 'active', 'revenue'):
        raise ValueError(f'unknown metric {metric!r}')

    User = get_user_model()

    today = timezone.now().date()
    # Anchor on Monday of the week N cohorts ago.
    current_week_start = _monday(today)
    earliest_cohort_start = current_week_start - timedelta(weeks=cohort_count - 1)

    # 1. Determine cohorts: customers grouped by their first-seen week.
    cohort_users = _cohort_users_by_week(User, earliest_cohort_start, current_week_start)

    # 2. Pull retention signals for every cohort × period intersection.
    rows: list[CohortRow] = []
    for offset in range(cohort_count):
        week_start = current_week_start - timedelta(weeks=cohort_count - 1 - offset)
        user_ids = list(cohort_users.get(week_start, []))
        size = len(user_ids)
        cells: list[CohortCell] = []

        for period in range(period_count):
            period_start = week_start + timedelta(weeks=period)
            period_end = period_start + timedelta(weeks=1)
            # No future periods.
            if period_start > today:
                cells.append(CohortCell())
                continue

            order_active = _count_users_with_order(user_ids, period_start, period_end)
            any_active = (
                _count_users_with_event(user_ids, period_start, period_end)
                if metric != 'order'
                else order_active
            )
            revenue = (
                _sum_revenue(user_ids, period_start, period_end)
                if metric == 'revenue'
                else Decimal('0')
            )

            order_pct = round((order_active / size) * 100, 1) if size else 0.0
            any_pct = round((any_active / size) * 100, 1) if size else 0.0

            cells.append(
                CohortCell(
                    customers=any_active if metric == 'active' else order_active,
                    retention_pct=any_pct if metric == 'active' else order_pct,
                    order_customers=order_active,
                    order_retention_pct=order_pct,
                    revenue=revenue,
                )
            )

        rows.append(
            CohortRow(
                week_start=week_start,
                week_label=week_start.strftime('%b %d'),
                size=size,
                cells=cells,
            )
        )

    return {
        'metric': metric,
        'periods': [f'W{p}' for p in range(period_count)],
        'rows': rows,
        'totals': {
            'customers': sum(r.size for r in rows),
            'cohorts': len([r for r in rows if r.size > 0]),
        },
    }


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _monday(d: date) -> date:
    """Return the Monday of the ISO week containing d."""
    return d - timedelta(days=d.weekday())


def _cohort_users_by_week(User, earliest: date, latest: date) -> dict[date, set[int]]:
    """Map week-start → set of user PKs created that week."""
    out: dict[date, set[int]] = defaultdict(set)
    end_dt = datetime.combine(latest + timedelta(days=7), datetime.min.time())
    start_dt = datetime.combine(earliest, datetime.min.time())
    qs = User.objects.filter(date_joined__gte=start_dt, date_joined__lt=end_dt).values(
        'id', 'date_joined'
    )
    for row in qs:
        joined = row['date_joined']
        if hasattr(joined, 'date'):
            joined = joined.date()
        week = _monday(joined)
        out[week].add(row['id'])
    return out


def _count_users_with_order(user_ids: list[int], start: date, end: date) -> int:
    """Count distinct user_ids who placed at least one order in [start, end)."""
    if not user_ids:
        return 0
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    return (
        Order.objects.filter(
            customer_id__in=user_ids,
            placed_at__gte=start,
            placed_at__lt=end,
        )
        .values('customer_id')
        .distinct()
        .count()
    )


def _count_users_with_event(user_ids: list[int], start: date, end: date) -> int:
    """Count distinct user_ids with any analytics event in [start, end)."""
    if not user_ids:
        return 0
    from plugins.installed.analytics.models import AnalyticsEvent  # noqa: PLC0415

    return (
        AnalyticsEvent.objects.filter(
            customer_id__in=user_ids,
            created_at__gte=start,
            created_at__lt=end,
        )
        .values('customer_id')
        .distinct()
        .count()
    )


def _sum_revenue(user_ids: list[int], start: date, end: date) -> Decimal:
    """Sum order totals for the cohort in this period."""
    if not user_ids:
        return Decimal('0')
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    agg = Order.objects.filter(
        customer_id__in=user_ids,
        placed_at__gte=start,
        placed_at__lt=end,
        status__in=('confirmed', 'paid', 'fulfilled', 'completed'),
    ).aggregate(total=Sum('total'))
    return Decimal(str(agg.get('total') or 0))


# ---------------------------------------------------------------------------
# Drop-off detail — which step in the funnel loses the most customers
# ---------------------------------------------------------------------------


def step_dropoffs(*, steps: list[str], days: int = 30) -> list[dict]:
    """For each consecutive step pair, return drop-off rate.

    Surfaced on the funnel dashboard so engineers can see *which*
    transition is the worst — not just the overall conversion rate.
    """
    from plugins.installed.analytics.services import funnel_for  # noqa: PLC0415

    rows = funnel_for(steps=steps, days=days)
    if not rows:
        return []
    out: list[dict] = []
    for i in range(1, len(rows)):
        prev = rows[i - 1]
        cur = rows[i]
        prev_n = prev.get('sessions') or 0
        cur_n = cur.get('sessions') or 0
        lost = max(0, prev_n - cur_n)
        rate = round((lost / prev_n) * 100, 1) if prev_n else 0.0
        out.append(
            {
                'from_step': prev['name'],
                'to_step': cur['name'],
                'prev_count': prev_n,
                'cur_count': cur_n,
                'lost': lost,
                'dropoff_pct': rate,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Period comparison — this period vs previous period
# ---------------------------------------------------------------------------


def period_comparison(*, days: int = 30) -> dict:
    """Compare orders + revenue this `days`-day period to the prior
    `days`-day period. Returns delta + percent change.
    """
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    now = timezone.now()
    this_start = now - timedelta(days=days)
    prev_start = this_start - timedelta(days=days)

    this_agg = Order.objects.filter(placed_at__gte=this_start).aggregate(
        n=Count('id'),
        rev=Sum('total'),
    )
    prev_agg = Order.objects.filter(placed_at__gte=prev_start, placed_at__lt=this_start).aggregate(
        n=Count('id'),
        rev=Sum('total'),
    )

    def pct_change(curr, prev):
        if not prev:
            return None
        return round(((curr - prev) / prev) * 100, 1)

    this_n = this_agg.get('n') or 0
    prev_n = prev_agg.get('n') or 0
    this_rev = Decimal(str(this_agg.get('rev') or 0))
    prev_rev = Decimal(str(prev_agg.get('rev') or 0))

    return {
        'days': days,
        'orders_this': this_n,
        'orders_prev': prev_n,
        'orders_delta': this_n - prev_n,
        'orders_pct_change': pct_change(this_n, prev_n),
        'revenue_this': this_rev,
        'revenue_prev': prev_rev,
        'revenue_delta': this_rev - prev_rev,
        'revenue_pct_change': pct_change(this_rev, prev_rev),
    }
