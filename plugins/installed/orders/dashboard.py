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
    """Append the sales / orders / average-order KPI tiles (``orders.reports``)."""
    from djmoney.money import Money  # noqa: PLC0415

    from core.templatetags.morph import money_filter  # noqa: PLC0415
    from core.utils.site import store_timezone  # noqa: PLC0415
    from plugins.installed.orders.models import Order  # noqa: PLC0415
    from plugins.installed.orders.reports import net_by_day, net_sales  # noqa: PLC0415

    sales = net_sales(
        Order.objects.filter(placed_at__gte=date_range.start, placed_at__lt=date_range.end)
    )
    prev = net_sales(
        Order.objects.filter(
            placed_at__gte=date_range.prev_start, placed_at__lt=date_range.prev_end
        )
    )
    revenue, order_count = sales.net, sales.orders
    prev_revenue, prev_count = prev.net, prev.orders
    avg_order = (revenue / order_count) if order_count else Decimal('0')
    currency = sales.currency or prev.currency or 'USD'

    def shown(amount) -> str:
        return money_filter(Money(amount, currency))

    # 14-day daily series for the sparklines, by the store's own day;
    # zero-filled so the visual stays comparable at any store volume.
    tz = store_timezone()
    today = timezone.now().astimezone(tz).date()
    keys = [(today - timedelta(days=i)) for i in range(13, -1, -1)]
    by_day = net_by_day(
        Order.objects.filter(placed_at__gte=timezone.now() - timedelta(days=15)), tz
    )
    rev_series = [float(by_day.get(k, (0, 0))[1]) for k in keys]
    cnt_series = [float(by_day.get(k, (0, 0))[0]) for k in keys]
    aov_series = [(rev_series[i] / cnt_series[i]) if cnt_series[i] else 0 for i in range(len(keys))]

    value.extend(
        [
            {
                'label': 'Total sales',
                'value': shown(revenue),
                'delta': _pct_delta(revenue, prev_revenue),
                'trend': _trend(revenue, prev_revenue),
                'icon': 'dollar-sign',
                'series': rev_series,
                'hint': 'Orders placed and not cancelled, after their refunds.',
            },
            {
                'label': 'Orders',
                'value': f'{order_count:,}',
                'delta': _pct_delta(order_count, prev_count),
                'trend': _trend(order_count, prev_count),
                'icon': 'shopping-bag',
                'series': cnt_series,
                'hint': 'Orders placed and not cancelled; unpaid ones left at checkout are not counted.',
            },
            {
                'label': 'Average order',
                'value': shown(avg_order) if order_count else '—',
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
