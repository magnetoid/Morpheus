"""Dashboard analytics — KPIs, time-series, breakdowns.

Reads directly from Order / OrderItem / Customer rather than the
hourly observability rollup so it works on day one without depending
on the Celery beat schedule. Falls back gracefully when any plugin
isn't installed.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import timedelta
from decimal import Decimal
from typing import Any

from morpheus.views import HttpRequest, HttpResponse, staff_member_required
from morpheus.views import render
from django.db.models import Count, Sum
from django.db.models.functions import (
    ExtractHour, ExtractWeekDay, TruncDate,
)

from plugins.installed.admin_dashboard.views_split._shared import (
    DATE_PRESETS, Metric, _pct_delta, _resolve_date_range, _trend, logger,
)


@staff_member_required
def analytics_view(request: HttpRequest) -> HttpResponse:
    date_range = _resolve_date_range(request)

    metrics: list[Metric] = []
    daily_series: list[dict] = []  # [{'day': date, 'rev': float, 'cnt': int}]
    top_products: list[dict] = []
    top_customers: list[dict] = []
    status_breakdown: list[dict] = []
    weekday_pattern: list[dict] = []
    hour_pattern: list[dict] = []
    revenue_total = Decimal('0')
    order_count = 0

    try:
        from plugins.installed.orders.models import Order, OrderItem

        orders_qs = Order.objects.filter(
            placed_at__gte=date_range.start,
            placed_at__lt=date_range.end,
        )
        prev_qs = Order.objects.filter(
            placed_at__gte=date_range.prev_start,
            placed_at__lt=date_range.prev_end,
        )

        order_count = orders_qs.count()
        prev_count = prev_qs.count()
        revenue_total = orders_qs.aggregate(t=Sum('total'))['t'] or Decimal('0')
        prev_revenue = prev_qs.aggregate(t=Sum('total'))['t'] or Decimal('0')
        avg_order = (revenue_total / order_count) if order_count else Decimal('0')
        prev_avg = (prev_revenue / prev_count) if prev_count else Decimal('0')

        # Daily series — fill zeros for missing days so charts always
        # span the full window edge-to-edge regardless of activity.
        bucketed = list(
            orders_qs
            .annotate(day=TruncDate('placed_at'))
            .values('day')
            .annotate(rev=Sum('total'), cnt=Count('id'))
            .order_by('day')
        )
        by_day = {row['day']: row for row in bucketed}
        cur = date_range.start.date()
        end = date_range.end.date()
        # Cap series at 366 buckets so long ranges stay performant in
        # the SVG chart. For >366d ranges we'd switch to weekly buckets;
        # not needed yet since the picker tops out at "this year".
        while cur < end and len(daily_series) < 366:
            row = by_day.get(cur)
            daily_series.append({
                'day': cur,
                'rev': float(row['rev']) if row and row['rev'] else 0.0,
                'cnt': int(row['cnt']) if row else 0,
            })
            cur += timedelta(days=1)

        rev_series = [d['rev'] for d in daily_series]
        cnt_series = [d['cnt'] for d in daily_series]

        metrics = [
            Metric(
                label='Revenue',
                value=f'${revenue_total:,.2f}',
                delta=_pct_delta(revenue_total, prev_revenue),
                trend=_trend(revenue_total, prev_revenue),
                icon='dollar-sign',
                series=rev_series,
            ),
            Metric(
                label='Orders',
                value=f'{order_count:,}',
                delta=_pct_delta(order_count, prev_count),
                trend=_trend(order_count, prev_count),
                icon='shopping-bag',
                series=cnt_series,
            ),
            Metric(
                label='Avg order',
                value=f'${avg_order:,.2f}' if order_count else '—',
                delta=_pct_delta(avg_order, prev_avg),
                trend=_trend(avg_order, prev_avg),
                icon='trending-up',
            ),
        ]

        # Top products by revenue.
        top_products = list(
            OrderItem.objects
            .filter(
                order__placed_at__gte=date_range.start,
                order__placed_at__lt=date_range.end,
            )
            .values('product_id', 'product_name')
            .annotate(
                units=Sum('quantity'),
                rev=Sum('total_price'),
            )
            .order_by('-rev')[:10]
        )

        # Order-status breakdown for the selected window.
        status_breakdown = list(
            orders_qs.values('status')
            .annotate(n=Count('id'))
            .order_by('-n')
        )

        # Day-of-week pattern. ExtractWeekDay returns 1=Sunday..7=Saturday
        # on Postgres; normalise to Mon-first for display.
        DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        wd_rows = (
            orders_qs.annotate(wd=ExtractWeekDay('placed_at'))
            .values('wd')
            .annotate(cnt=Count('id'), rev=Sum('total'))
        )
        # Map weekday → counts; convert SQL-1..7 (Sun..Sat) into 0..6 (Mon..Sun).
        bucket: dict[int, dict] = OrderedDict((i, {'cnt': 0, 'rev': 0.0}) for i in range(7))
        for r in wd_rows:
            sql_wd = int(r['wd'] or 1)
            mon_first = (sql_wd + 5) % 7  # 1(Sun)→6, 2(Mon)→0, …
            bucket[mon_first]['cnt'] += int(r['cnt'] or 0)
            bucket[mon_first]['rev'] += float(r['rev'] or 0)
        weekday_pattern = [
            {'label': DAY_LABELS[i], **bucket[i]} for i in range(7)
        ]

        # Hour-of-day pattern.
        hr_rows = (
            orders_qs.annotate(h=ExtractHour('placed_at'))
            .values('h')
            .annotate(cnt=Count('id'))
        )
        hr_by = {int(r['h'] or 0): int(r['cnt'] or 0) for r in hr_rows}
        hour_pattern = [{'h': h, 'cnt': hr_by.get(h, 0)} for h in range(24)]

        # Top customers by spend in window.
        top_customers = list(
            orders_qs
            .values('customer_id', 'email')
            .annotate(orders=Count('id'), spend=Sum('total'))
            .order_by('-spend')[:10]
        )
    except Exception as e:  # noqa: BLE001 — orders plugin optional
        logger.warning('analytics: orders panel error: %s', e, exc_info=True)

    new_customers = 0
    try:
        from plugins.installed.customers.models import Customer
        new_customers = Customer.objects.filter(
            date_joined__gte=date_range.start,
            date_joined__lt=date_range.end,
        ).count()
        metrics.append(Metric(
            label='New customers',
            value=f'{new_customers:,}',
            icon='user-plus',
        ))
    except Exception as e:  # noqa: BLE001
        logger.debug('analytics: customers panel skipped: %s', e)

    # Refund volume — sum of refund amounts in the window.
    try:
        from plugins.installed.orders.refunds import Refund
        ref_total = Refund.objects.filter(
            created_at__gte=date_range.start,
            created_at__lt=date_range.end,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        if ref_total or revenue_total:
            metrics.append(Metric(
                label='Refunded',
                value=f'${ref_total:,.2f}',
                icon='undo-2',
            ))
    except Exception as e:  # noqa: BLE001
        logger.debug('analytics: refunds panel skipped: %s', e)

    # Build SVG points for the daily revenue chart up front so the
    # template stays presentational.
    chart_w, chart_h = 880, 220
    chart_pad_l, chart_pad_r, chart_pad_b, chart_pad_t = 44, 16, 28, 12
    plot_w = chart_w - chart_pad_l - chart_pad_r
    plot_h = chart_h - chart_pad_t - chart_pad_b
    rev_max = max((d['rev'] for d in daily_series), default=0.0)
    if rev_max <= 0:
        rev_max = 1.0  # avoid div-by-zero on empty windows
    n = len(daily_series)
    chart_points: list[tuple[float, float, dict]] = []
    if n > 1:
        step = plot_w / (n - 1)
        for i, d in enumerate(daily_series):
            x = chart_pad_l + i * step
            y = chart_pad_t + plot_h - (d['rev'] / rev_max) * plot_h
            chart_points.append((round(x, 2), round(y, 2), d))
    chart_polyline = ' '.join(f'{x},{y}' for x, y, _ in chart_points)
    # Area fill — close the polyline back to the baseline.
    chart_area = ''
    if chart_points:
        first_x, _, _ = chart_points[0]
        last_x, _, _ = chart_points[-1]
        baseline_y = chart_pad_t + plot_h
        chart_area = (
            f'{first_x},{baseline_y} '
            + chart_polyline
            + f' {last_x},{baseline_y}'
        )
    # Y-axis ticks at 0%, 50%, 100% of max.
    chart_yticks = [
        {'y': chart_pad_t + plot_h, 'label': '$0'},
        {'y': chart_pad_t + plot_h / 2, 'label': f'${rev_max/2:,.0f}'},
        {'y': chart_pad_t,            'label': f'${rev_max:,.0f}'},
    ]

    # Pre-compute max bar values so the template can scale via widthratio.
    weekday_max = max((w['cnt'] for w in weekday_pattern), default=0) or 1
    hour_max = max((h['cnt'] for h in hour_pattern), default=0) or 1

    return render(request, 'admin_dashboard/analytics.html', {
        'date_range': date_range,
        'date_presets': DATE_PRESETS,
        'metrics': metrics,
        'daily_series': daily_series,
        'chart_w': chart_w,
        'chart_h': chart_h,
        'chart_pad_l': chart_pad_l,
        'chart_polyline': chart_polyline,
        'chart_area': chart_area,
        'chart_points': chart_points,
        'chart_yticks': chart_yticks,
        'top_products': top_products,
        'top_customers': top_customers,
        'status_breakdown': status_breakdown,
        'weekday_pattern': weekday_pattern,
        'weekday_max': weekday_max,
        'hour_pattern': hour_pattern,
        'hour_max': hour_max,
        'new_customers': new_customers,
        'active_nav': 'analytics',
    })


# ── Marketing ─────────────────────────────────────────────────────────────────
