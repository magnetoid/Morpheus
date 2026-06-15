"""Auto-split from the legacy admin_dashboard/views.py monolith."""

# Lazy imports inside the fail-soft tile blocks are intentional: a broken
# or missing optional plugin must not 500 the dashboard home page.
# ruff: noqa: PLC0415

from __future__ import annotations

import contextlib

from morpheus.views import (
    HttpRequest,
    HttpResponse,
    render,
    staff_member_required,
)
from plugins.installed.admin_dashboard.views_split._shared import (
    DATE_PRESETS,
    _resolve_date_range,
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
def dashboard_home(request: HttpRequest) -> HttpResponse:
    """Dashboard home. Every tile's data is contributed by its owning
    plugin through filters (see core/hooks.py + docs/plans/
    dashboard-home-modular.md): DASHBOARD_KPIS (metric row),
    DASHBOARD_HOME_PANELS (recent orders / top products / insights /
    pulse / ai_summary / low stock) and DASHBOARD_SETUP_STEPS — so a
    disabled plugin's tile simply never renders and this view imports
    no plugin models. ACTIVITY_FEED feeds the activity column the same
    way.
    """
    from core.hooks import MorpheusEvents, hook_registry

    date_range = _resolve_date_range(request)
    period = date_range.preset or 'custom'

    metrics: list = []
    with _safe_block('home.kpis'):
        metrics = hook_registry.filter(
            MorpheusEvents.DASHBOARD_KPIS, value=metrics, date_range=date_range
        )

    panels: dict = {}
    with _safe_block('home.panels'):
        panels = hook_registry.filter(
            MorpheusEvents.DASHBOARD_HOME_PANELS, value=panels, date_range=date_range
        )
    ai_summary = panels.get('ai_summary') or {
        'agent_count': 0,
        'recent_runs': 0,
        'unread_insights': 0,
        'provider': '',
        'has_keys': False,
    }

    setup_steps = _compute_setup_steps()
    setup_done = sum(1 for s in setup_steps if s['done'])
    setup_total = len(setup_steps)
    setup_all_done = setup_total > 0 and setup_done == setup_total

    activity = _compute_activity_feed(limit=20)

    return render(
        request,
        'admin_dashboard/home.html',
        {
            'metrics': metrics,
            'recent_orders': panels.get('recent_orders', []),
            'top_products': panels.get('top_products', []),
            'insights': panels.get('insights', []),
            'ai_summary': ai_summary,
            'low_stock': panels.get('low_stock', []),
            'low_stock_threshold': panels.get('low_stock_threshold', 0),
            'setup_steps': setup_steps,
            'setup_done': setup_done,
            'setup_total': setup_total,
            'setup_all_done': setup_all_done,
            'activity': activity,
            'pulse': panels.get('pulse', []),
            'active_nav': 'home',
            'period': period,
            'date_range': date_range,
            'date_presets': DATE_PRESETS,
        },
    )


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
        # Drop entries with no timestamp and sort inside the safe block: a
        # contributed item with a missing/None `when` (open plugin contract)
        # must degrade to a hidden tile, never 500 the whole home page.
        items = [it for it in items if it.get('when') is not None]
        items.sort(key=lambda it: it['when'], reverse=True)
        items = items[:limit]
    return items


def _compute_setup_steps() -> list:
    """Build the first-time merchant setup checklist.

    Steps are contributed through the ``DASHBOARD_SETUP_STEPS`` filter
    (catalog → first product, orders → first order, ai_assistant →
    provider key), so a disabled plugin's step disappears. The sending-
    email step reads core settings — no plugin owns it — and is
    appended here so it always lands last.
    """
    from django.conf import settings as dj_settings

    from core.hooks import MorpheusEvents, hook_registry

    steps: list = []
    with _safe_block('setup.steps'):
        steps = hook_registry.filter(MorpheusEvents.DASHBOARD_SETUP_STEPS, value=steps)
    steps.append(
        {
            'key': 'email',
            'label': 'Set a sending email',
            'hint': 'So order confirmations and receipts can go out.',
            'url': '/dashboard/settings/general/',
            'done': bool(getattr(dj_settings, 'DEFAULT_FROM_EMAIL', '') or ''),
        }
    )
    return steps


# ── Orders ────────────────────────────────────────────────────────────────────
