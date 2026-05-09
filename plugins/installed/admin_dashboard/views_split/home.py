"""Auto-split from the legacy admin_dashboard/views.py monolith."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from morpheus.views import HttpRequest, HttpResponse, messages, staff_member_required
from morpheus.views import get_object_or_404, redirect, render
from django.db.models import Sum
from django.utils import timezone

from plugins.installed.admin_dashboard.forms import (
    AddressForm,
    CouponForm,
    CustomerForm,
    DraftOrderForm,
    FulfillmentForm,
    ProductForm,
    RefundForm,
    VariantForm,
)
from plugins.installed.admin_dashboard.views_split._shared import (
    DATE_PRESETS, Metric, _bulk_ids, _period, _pct_delta, _resolve_date_range,
    _since, _sparkline_points, _trend, logger,
)

@staff_member_required
def dashboard_home(request: HttpRequest) -> HttpResponse:
    date_range = _resolve_date_range(request)
    period = date_range.preset or 'custom'
    days = date_range.days
    since = date_range.start

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
        from datetime import date as _date, timedelta as _td
        today = timezone.now().date()
        keys = [(today - _td(days=i)) for i in range(13, -1, -1)]
        rev_by_day = {
            row['day']: row['v']
            for row in (Order.objects
                .filter(placed_at__gte=spark_since)
                .annotate(day=TruncDate('placed_at'))
                .values('day')
                .annotate(v=Sum('total'))
            )
        }
        cnt_by_day = {
            row['day']: row['v']
            for row in (Order.objects
                .filter(placed_at__gte=spark_since)
                .annotate(day=TruncDate('placed_at'))
                .values('day')
                .annotate(v=Count('id'))
            )
        }
        rev_series = [float(rev_by_day.get(k, 0) or 0) for k in keys]
        cnt_series = [float(cnt_by_day.get(k, 0) or 0) for k in keys]
        aov_series = [(rev_series[i] / cnt_series[i]) if cnt_series[i] else 0 for i in range(len(keys))]

        metrics.extend([
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
        ])

        recent_orders = list(
            Order.objects
            .select_related('customer', 'channel')
            .order_by('-placed_at')[:6]
        )
    except Exception as e:  # noqa: BLE001 — plugin optional / fail soft
        logger.warning('admin_dashboard: orders panel error: %s', e, exc_info=True)

    try:
        from plugins.installed.catalog.models import Product

        active_count = Product.objects.filter(status='active').count()
        metrics.append(Metric(
            label='Active products',
            value=f'{active_count:,}',
            icon='package',
        ))
        top_products = list(
            Product.objects.filter(status='active')
            .order_by('-created_at')[:5]
        )
    except Exception as e:  # noqa: BLE001
        logger.warning('admin_dashboard: catalog panel error: %s', e, exc_info=True)

    try:
        from plugins.installed.ai_assistant.models import MerchantInsight
        insights = list(
            MerchantInsight.objects
            .filter(is_read=False)
            .order_by('-created_at')[:4]
        )
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
    try:
        from plugins.registry import plugin_registry
        ai_plugin = plugin_registry.get('ai_assistant')
        if ai_plugin is not None:
            cfg = ai_plugin.get_config()
            ai_summary['provider'] = cfg.get('ai_provider') or 'openai'
            ai_summary['has_keys'] = any(
                cfg.get(k) for k in (
                    'openai_api_key', 'anthropic_api_key', 'gemini_api_key',
                    'openrouter_api_key', 'ollama_api_key',
                )
            )
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.agent_core.models import Agent, AgentRun
        ai_summary['agent_count'] = Agent.objects.filter(is_active=True).count()
        ai_summary['recent_runs'] = AgentRun.objects.filter(
            created_at__gte=_since(7),
        ).count()
    except Exception:  # noqa: BLE001
        pass

    # Stock alerts — surface on home only when at least one variant is
    # below threshold. Inventory + advanced_ecommerce both optional.
    low_stock: list[Any] = []
    low_stock_threshold = 0
    try:
        from plugins.installed.inventory.models import StockLevel
        from plugins.registry import plugin_registry
        ae_plugin = plugin_registry.get('advanced_ecommerce')
        low_stock_threshold = (
            int(ae_plugin.get_config_value('low_stock_threshold', 5))
            if ae_plugin else 5
        )
        # available_quantity is a Python property; pull a small page and
        # filter in-memory so we don't need a denormalised column.
        candidates = list(
            StockLevel.objects
            .select_related('variant', 'variant__product', 'warehouse')
            .filter(quantity__lte=low_stock_threshold + 50)[:200]
        )
        low_stock = sorted(
            (sl for sl in candidates if sl.available_quantity <= low_stock_threshold),
            key=lambda sl: sl.available_quantity,
        )[:6]
    except Exception:  # noqa: BLE001
        pass

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

    return render(request, 'admin_dashboard/home.html', {
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
        'active_nav': 'home',
        'period': period,
        'date_range': date_range,
        'date_presets': DATE_PRESETS,
    })


def _compute_activity_feed(limit: int = 20) -> list:
    """Recent platform events as a single chronological list.

    Pulls from three sources without coupling them together — each is
    a separate fail-soft try block:

      * orders.OrderEvent          (placed, paid, fulfilled, cancelled)
      * orders.ReturnRequest       (state transitions)
      * agent_core.AgentRun        (recent agent runs)

    Each entry is a uniform dict — kind, label, hint, url, icon, when —
    so the template renders them with one component. Sorted newest first.
    """
    items: list[dict] = []

    try:
        from plugins.installed.orders.models import OrderEvent
        for ev in (
            OrderEvent.objects
            .select_related('order')
            .order_by('-created_at')[: limit * 2]
        ):
            verb = (ev.event_type or 'updated').replace('_', ' ').replace('.', ' ')
            items.append({
                'kind': 'order',
                'icon': 'shopping-bag',
                'label': f'Order #{ev.order.order_number} — {verb}',
                'hint': ev.message or '',
                'url': f'/dashboard/orders/{ev.order.order_number}/',
                'when': ev.created_at,
            })
    except Exception:  # noqa: BLE001
        pass

    try:
        from plugins.installed.orders.refunds import ReturnRequest
        for rr in (
            ReturnRequest.objects
            .select_related('order')
            .order_by('-updated_at')[: limit]
        ):
            items.append({
                'kind': 'return',
                'icon': 'undo-2',
                'label': f'RMA {rr.rma_number} — {rr.get_state_display()}',
                'hint': f'Order #{rr.order.order_number}',
                'url': f'/dashboard/returns/{rr.id}/',
                'when': rr.updated_at,
            })
    except Exception:  # noqa: BLE001
        pass

    try:
        from plugins.installed.agent_core.models import AgentRun
        for run in (
            AgentRun.objects
            .order_by('-started_at')[: limit]
        ):
            label = f'Agent: {run.agent_name}'
            if run.state == 'failed':
                label += ' — failed'
            elif run.state == 'awaiting_approval':
                label += ' — needs approval'
            items.append({
                'kind': 'agent',
                'icon': 'bot',
                'label': label,
                'hint': (run.user_message or '')[:80],
                'url': f'/dashboard/agents/runs/{run.id}/',
                'when': run.started_at,
            })
    except Exception:  # noqa: BLE001
        pass

    try:
        from plugins.installed.reviews.models import Review
        for r in (
            Review.objects.select_related('product', 'customer')
            .order_by('-created_at')[: limit]
        ):
            who = (r.customer.email if r.customer else 'a reader')
            items.append({
                'kind': 'review',
                'icon': 'star',
                'label': f'New review on {r.product.name} ({r.rating}/5)',
                'hint': f'by {who}',
                'url': f'/admin/reviews/review/{r.id}/change/',
                'when': r.created_at,
            })
    except Exception:  # noqa: BLE001
        pass

    try:
        from plugins.installed.loyalty_points.models import PointsTransaction
        for tx in (
            PointsTransaction.objects.select_related('customer')
            .filter(reason='earn_order')
            .order_by('-created_at')[: limit]
        ):
            who = tx.customer.email if tx.customer else 'a reader'
            items.append({
                'kind': 'loyalty',
                'icon': 'award',
                'label': f'+{tx.points} reader points to {who}',
                'hint': tx.note or f'Order #{tx.order_number}',
                'url': f'/dashboard/customers/?q={who}',
                'when': tx.created_at,
            })
    except Exception:  # noqa: BLE001
        pass

    try:
        from plugins.installed.crm.models import Lead
        for lead in (
            Lead.objects.filter(source='newsletter')
            .order_by('-created_at')[: limit]
        ):
            items.append({
                'kind': 'newsletter',
                'icon': 'mail',
                'label': f'Newsletter signup: {lead.email}',
                'hint': '',
                'url': f'/dashboard/crm/leads/{lead.id}/',
                'when': lead.created_at,
            })
    except Exception:  # noqa: BLE001
        pass

    # Sort newest first, drop the trailing items past the cap.
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
    try:
        from plugins.installed.catalog.models import Product
        has_product = Product.objects.exists()
    except Exception:  # noqa: BLE001
        pass
    steps.append({
        'key': 'product',
        'label': 'Add your first product',
        'hint': 'Create a product to put on the shelf.',
        'url': '/dashboard/products/new/',
        'done': has_product,
    })
    # 2) at least one order (test or real)
    has_order = False
    try:
        from plugins.installed.orders.models import Order
        has_order = Order.objects.exists()
    except Exception:  # noqa: BLE001
        pass
    steps.append({
        'key': 'order',
        'label': 'Receive a test order',
        'hint': 'Place an order through the storefront, or use Draft orders.',
        'url': '/dashboard/orders/',
        'done': has_order,
    })
    # 3) AI provider configured
    ai_done = False
    try:
        from plugins.installed.ai_assistant.services.config import get_provider_config
        ai_done = bool(get_provider_config().api_key)
    except Exception:  # noqa: BLE001
        pass
    steps.append({
        'key': 'ai',
        'label': 'Connect an AI provider',
        'hint': 'OpenAI / Anthropic / Gemini / OpenRouter / Ollama.',
        'url': '/dashboard/settings/ai/',
        'done': ai_done,
    })
    # 4) email sender configured (DEFAULT_FROM_EMAIL)
    from django.conf import settings as dj_settings
    email_done = bool(getattr(dj_settings, 'DEFAULT_FROM_EMAIL', '') or '')
    steps.append({
        'key': 'email',
        'label': 'Set a sending email',
        'hint': 'So order confirmations and receipts can go out.',
        'url': '/dashboard/settings/general/',
        'done': email_done,
    })
    return steps


# ── Orders ────────────────────────────────────────────────────────────────────


