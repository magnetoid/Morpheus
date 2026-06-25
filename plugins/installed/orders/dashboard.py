"""Dashboard-home contributions from the orders plugin.

Subscribed by ``OrdersPlugin.ready()`` on the ``DASHBOARD_KPIS``,
``DASHBOARD_HOME_PANELS`` and ``DASHBOARD_SETUP_STEPS`` filters
(see core/hooks.py). The KPI dicts are duck-typed stand-ins for the
dashboard's Metric rows — admin_dashboard must stay import-free of
this plugin and vice versa, so the tiny delta/trend helpers are local.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone


def _trend(now, before) -> str:
    if not before:
        return 'flat'
    if now > before:
        return 'up'
    if now < before:
        return 'down'
    return 'flat'


def _pct_delta(now, before) -> str:
    if not before:
        return '—'
    diff = (Decimal(now) - Decimal(before)) / Decimal(before) * Decimal('100')
    sign = '+' if diff >= 0 else ''
    return f'{sign}{diff:.1f}%'


def on_dashboard_kpis(value, date_range=None, **kwargs):
    """Append the sales / orders / average-order KPI tiles."""
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    orders_qs = Order.objects.filter(
        placed_at__gte=date_range.start,
        placed_at__lt=date_range.end,
    )
    order_count = orders_qs.count()
    revenue = orders_qs.aggregate(total=Sum('total'))['total'] or Decimal('0')
    avg_order = (revenue / order_count) if order_count else Decimal('0')

    prev_orders = Order.objects.filter(
        placed_at__gte=date_range.prev_start,
        placed_at__lt=date_range.prev_end,
    )
    prev_count = prev_orders.count()
    prev_revenue = prev_orders.aggregate(total=Sum('total'))['total'] or Decimal('0')

    # 14-day daily series for the sparklines. One aggregate query each;
    # zero-filled so the visual stays comparable at any store volume.
    today = timezone.now().date()
    spark_since = timezone.now() - timedelta(days=14)
    keys = [(today - timedelta(days=i)) for i in range(13, -1, -1)]
    rev_by_day = {
        row['day']: row['v']
        for row in (
            Order.objects.filter(placed_at__gte=spark_since)
            .annotate(day=TruncDate('placed_at'))
            .values('day')
            .annotate(v=Sum('total'))
        )
    }
    cnt_by_day = {
        row['day']: row['v']
        for row in (
            Order.objects.filter(placed_at__gte=spark_since)
            .annotate(day=TruncDate('placed_at'))
            .values('day')
            .annotate(v=Count('id'))
        )
    }
    rev_series = [float(rev_by_day.get(k, 0) or 0) for k in keys]
    cnt_series = [float(cnt_by_day.get(k, 0) or 0) for k in keys]
    aov_series = [(rev_series[i] / cnt_series[i]) if cnt_series[i] else 0 for i in range(len(keys))]

    value.extend(
        [
            {
                'label': 'Total sales',
                'value': f'${revenue:,.2f}',
                'delta': _pct_delta(revenue, prev_revenue),
                'trend': _trend(revenue, prev_revenue),
                'icon': 'dollar-sign',
                'series': rev_series,
                'hint': 'Gross revenue from all placed orders (before refunds).',
            },
            {
                'label': 'Orders',
                'value': f'{order_count:,}',
                'delta': _pct_delta(order_count, prev_count),
                'trend': _trend(order_count, prev_count),
                'icon': 'shopping-bag',
                'series': cnt_series,
                'hint': 'Total number of completed checkout sessions.',
            },
            {
                'label': 'Average order',
                'value': f'${avg_order:,.2f}' if order_count else '—',
                'delta': '',
                'trend': 'flat',
                'icon': 'trending-up',
                'series': aov_series,
                'hint': 'Average revenue per placed order (Total sales ÷ Orders).',
            },
        ]
    )
    return value


def on_dashboard_panels(value, date_range=None, **kwargs):
    """Fold the recent-orders panel into the home context."""
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    value['recent_orders'] = list(
        Order.objects.select_related('customer', 'channel').order_by('-placed_at')[:6]
    )
    return value


def on_setup_steps(value, **kwargs):
    """Append the 'receive a test order' first-run step."""
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    value.append(
        {
            'key': 'order',
            'label': 'Receive a test order',
            'hint': 'Place an order through the storefront, or use Draft orders.',
            'url': '/dashboard/orders/',
            'done': Order.objects.exists(),
        }
    )
    return value
