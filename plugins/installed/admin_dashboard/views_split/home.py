"""Auto-split from the legacy admin_dashboard/views.py monolith."""

# Lazy imports inside the fail-soft tile blocks are intentional: a broken
# or missing optional plugin must not 500 the dashboard home page.
# ruff: noqa: PLC0415

from __future__ import annotations

import contextlib
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.utils import timezone

from morpheus.views import (
    HttpRequest,
    HttpResponse,
    messages,
    redirect,
    render,
    staff_member_required,
)
from plugins.installed.admin_dashboard.views_split._shared import (
    DATE_PRESETS,
    Metric,
    _pct_delta,
    _resolve_date_range,
    _since,
    _trend,
    logger,
)


@contextlib.contextmanager
def _safe_block(label: str):
    """Swallow any exception from a dashboard tile so one broken plugin
    doesn't 500 the home page — but log it with traceback so silent
    feature outages stop hiding.
    """
    try:
        yield
    except Exception as e:  # noqa: BLE001
        logger.warning('dashboard tile %s failed: %s', label, e, exc_info=True)


@staff_member_required
def dashboard_home(request: HttpRequest) -> HttpResponse:  # noqa: PLR0915 — one statement per tile
    date_range = _resolve_date_range(request)
    period = date_range.preset or 'custom'

    metrics: list[Metric] = []
    recent_orders: list[Any] = []
    top_products: list[Any] = []
    insights: list[Any] = []

    try:
        from django.db.models import Count
        from django.db.models.functions import TruncDate

        from plugins.installed.orders.models import Order

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

        # 14-day daily series for the sparklines on each KPI tile. One
        # aggregate query each — cheap. We fill in zero for missing days
        # so the visual stays comparable across stores at any volume.
        spark_since = _since(14)
        from datetime import timedelta as _td

        today = timezone.now().date()
        keys = [(today - _td(days=i)) for i in range(13, -1, -1)]
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
        aov_series = [
            (rev_series[i] / cnt_series[i]) if cnt_series[i] else 0 for i in range(len(keys))
        ]

        metrics.extend(
            [
                Metric(
                    label='Total sales',
                    value=f'${revenue:,.2f}',
                    delta=_pct_delta(revenue, prev_revenue),
                    trend=_trend(revenue, prev_revenue),
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
                    label='Average order',
                    value=f'${avg_order:,.2f}' if order_count else '—',
                    icon='trending-up',
                    series=aov_series,
                ),
            ]
        )

        recent_orders = list(
            Order.objects.select_related('customer', 'channel').order_by('-placed_at')[:6]
        )
    except Exception as e:  # noqa: BLE001 — plugin optional / fail soft
        logger.warning('admin_dashboard: orders panel error: %s', e, exc_info=True)

    try:
        from plugins.installed.catalog.models import Product

        active_count = Product.objects.filter(status='active').count()
        metrics.append(
            Metric(
                label='Active products',
                value=f'{active_count:,}',
                icon='package',
            )
        )
        top_products = list(Product.objects.filter(status='active').order_by('-created_at')[:5])
    except Exception as e:  # noqa: BLE001
        logger.warning('admin_dashboard: catalog panel error: %s', e, exc_info=True)

    try:
        from plugins.installed.ai_assistant.models import MerchantInsight

        insights = list(MerchantInsight.objects.filter(is_read=False).order_by('-created_at')[:4])
    except Exception as e:  # noqa: BLE001
        logger.debug('admin_dashboard: insights panel skipped: %s', e)

    # AI summary block: counts of active agents + recent runs + provider in
    # use. Fail-soft if agent_core / ai_assistant aren't installed.
    ai_summary: dict[str, Any] = {
        'agent_count': 0,
        'recent_runs': 0,
        'unread_insights': len(insights),
        'provider': '',
        'has_keys': False,
    }
    with _safe_block('ai_summary.provider'):
        from plugins.registry import plugin_registry

        ai_plugin = plugin_registry.get('ai_assistant')
        if ai_plugin is not None:
            cfg = ai_plugin.get_config()
            ai_summary['provider'] = cfg.get('ai_provider') or 'openai'
            ai_summary['has_keys'] = any(
                cfg.get(k)
                for k in (
                    'openai_api_key',
                    'anthropic_api_key',
                    'gemini_api_key',
                    'openrouter_api_key',
                    'grok_api_key',
                    'packy_api_key',
                    'ollama_api_key',
                )
            )
    with _safe_block('ai_summary.agent_runs'):
        from plugins.installed.agent_core.models import Agent, AgentRun

        ai_summary['agent_count'] = Agent.objects.filter(is_active=True).count()
        ai_summary['recent_runs'] = AgentRun.objects.filter(
            created_at__gte=_since(7),
        ).count()

    # Stock alerts — surface on home only when at least one variant is
    # below threshold. Inventory + advanced_ecommerce both optional.
    low_stock: list[Any] = []
    low_stock_threshold = 0
    with _safe_block('low_stock_tile'):
        from plugins.installed.inventory.models import StockLevel
        from plugins.registry import plugin_registry

        ae_plugin = plugin_registry.get('advanced_ecommerce')
        low_stock_threshold = (
            int(ae_plugin.get_config_value('low_stock_threshold', 5)) if ae_plugin else 5
        )
        # available_quantity is a Python property; pull a small page and
        # filter in-memory so we don't need a denormalised column.
        candidates = list(
            StockLevel.objects.select_related('variant', 'variant__product', 'warehouse').filter(
                quantity__lte=low_stock_threshold + 50
            )[:200]
        )
        low_stock = sorted(
            (sl for sl in candidates if sl.available_quantity <= low_stock_threshold),
            key=lambda sl: sl.available_quantity,
        )[:6]

    # First-run checklist — only shown for empty/very-new stores so it
    # doesn't get in the way once the merchant is rolling. We compute
    # each step on the fly; cheap counts only. When everything's done
    # the template hides the whole card.
    setup_steps = _compute_setup_steps()
    setup_done = sum(1 for s in setup_steps if s['done'])
    setup_total = len(setup_steps)
    setup_all_done = setup_total > 0 and setup_done == setup_total

    # Activity feed — what happened lately, across all event sources.
    activity = _compute_activity_feed(limit=20)

    # Linda's Pulse — top-5 ranked unread insight cards.
    pulse: list = []
    with _safe_block('pulse_tile'):
        from plugins.installed.ai_assistant.models import MerchantInsight

        _PRIO = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        rows = list(MerchantInsight.objects.filter(is_read=False))
        rows.sort(key=lambda r: (_PRIO.get(r.priority, 9), -r.created_at.timestamp()))
        pulse = rows[:5]

    return render(
        request,
        'admin_dashboard/home.html',
        {
            'metrics': metrics,
            'recent_orders': recent_orders,
            'top_products': top_products,
            'insights': insights,
            'ai_summary': ai_summary,
            'low_stock': low_stock,
            'low_stock_threshold': low_stock_threshold,
            'setup_steps': setup_steps,
            'setup_done': setup_done,
            'setup_total': setup_total,
            'setup_all_done': setup_all_done,
            'activity': activity,
            'pulse': pulse,
            'active_nav': 'home',
            'period': period,
            'date_range': date_range,
            'date_presets': DATE_PRESETS,
        },
    )


@staff_member_required
def pulse_refresh(request: HttpRequest) -> HttpResponse:
    """Force a Pulse regeneration on demand. Sync — small enough to not need a task."""
    if request.method != 'POST':
        return redirect('/dashboard/')
    try:
        from plugins.installed.ai_assistant.services.pulse import generate_pulse_insights

        generate_pulse_insights()
    except Exception as e:  # noqa: BLE001
        messages.error(request, f'Pulse refresh failed: {e}')
    else:
        messages.success(request, 'Pulse refreshed.')
    return redirect('/dashboard/')


@staff_member_required
def pulse_dismiss(request: HttpRequest, insight_id: str) -> HttpResponse:
    """Mark a Pulse card read so it falls off the panel."""
    if request.method != 'POST':
        return redirect('/dashboard/')
    with _safe_block('pulse_dismiss'):
        from plugins.installed.ai_assistant.models import MerchantInsight

        MerchantInsight.objects.filter(id=insight_id).update(is_read=True)
    return redirect('/dashboard/')


def _compute_activity_feed(limit: int = 20) -> list:
    """Recent platform events as a single chronological list.

    Assembled through the ``ACTIVITY_FEED`` filter (see core/hooks.py):
    each enabled plugin appends its own recent-event dicts — kind, label,
    hint, url, icon, when — so this view knows nothing about sibling
    plugins' models, and a disabled plugin's entries simply never appear.
    orders, agent_core, reviews, loyalty_points and crm all subscribe.
    Sorted newest first, capped at `limit`.
    """
    from core.hooks import MorpheusEvents, hook_registry

    items: list[dict] = []
    with _safe_block('activity.feed'):
        items = hook_registry.filter(MorpheusEvents.ACTIVITY_FEED, value=items, limit=limit)

    items.sort(key=lambda it: it['when'], reverse=True)
    return items[:limit]


def _compute_setup_steps() -> list:
    """Build the first-time merchant setup checklist.

    Returns a list of dicts (key, label, hint, url, done). Skipped from
    the home page entirely when every step is done — see template
    guard. Cheap: 4 small COUNT queries; runs only on the home view.
    """
    steps = []
    # 1) at least one product
    has_product = False
    with _safe_block('setup.has_product'):
        from plugins.installed.catalog.models import Product

        has_product = Product.objects.exists()
    steps.append(
        {
            'key': 'product',
            'label': 'Add your first product',
            'hint': 'Create a product to put on the shelf.',
            'url': '/dashboard/products/new/',
            'done': has_product,
        }
    )
    # 2) at least one order (test or real)
    has_order = False
    with _safe_block('setup.has_order'):
        from plugins.installed.orders.models import Order

        has_order = Order.objects.exists()
    steps.append(
        {
            'key': 'order',
            'label': 'Receive a test order',
            'hint': 'Place an order through the storefront, or use Draft orders.',
            'url': '/dashboard/orders/',
            'done': has_order,
        }
    )
    # 3) AI provider configured
    ai_done = False
    with _safe_block('setup.ai_provider'):
        from plugins.installed.ai_assistant.services.config import get_provider_config

        ai_done = bool(get_provider_config().api_key)
    steps.append(
        {
            'key': 'ai',
            'label': 'Connect an AI provider',
            'hint': 'OpenAI / Anthropic / Gemini / OpenRouter / Ollama.',
            'url': '/dashboard/settings/ai/',
            'done': ai_done,
        }
    )
    # 4) email sender configured (DEFAULT_FROM_EMAIL)
    from django.conf import settings as dj_settings

    email_done = bool(getattr(dj_settings, 'DEFAULT_FROM_EMAIL', '') or '')
    steps.append(
        {
            'key': 'email',
            'label': 'Set a sending email',
            'hint': 'So order confirmations and receipts can go out.',
            'url': '/dashboard/settings/general/',
            'done': email_done,
        }
    )
    return steps


# ── Orders ────────────────────────────────────────────────────────────────────
