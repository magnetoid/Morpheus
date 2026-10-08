"""Plugin context processor — exposes the active apps and their contributions,
and merges app-contributed context processors (register_context_processor).

The dashboard's navigation (sidebar sections, tabs, settings categories, nav
badges) is not built here: it is the shell's job and runs for dashboard
requests only — `admin_dashboard/context_processors.dashboard_nav`. It used
to be computed in this processor for every request, storefront included,
which cost every shopper page three badge queries."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def plugin_context(request):
    from plugins.registry import app_registry

    out = {
        'active_plugins': app_registry._active,
        'app_registry': app_registry,
        'dashboard_pages': app_registry.dashboard_pages(),  # back-compat flat list
        # Schema-driven settings panels (form-based).
        'plugin_settings_panels': app_registry.all_settings_panels(),
    }

    # Plugin-contributed context processors (register_context_processor). Django
    # resolves its TEMPLATES list at settings-import — before plugins load — so
    # these are merged HERE, at request time, instead of being listed directly.
    # Each runs only while its owning plugin is active (context processors are
    # not bus-gated like hooks), and a broken one is isolated so it can't 500
    # the page. This is the consumer that makes register_context_processor real.
    for func, owner in app_registry.context_processors():
        if owner and not app_registry.is_active(owner):
            continue
        try:
            extra = func(request)
        except Exception:  # noqa: BLE001 — a broken contributor must not break rendering
            logger.warning(
                'context processor %s failed', getattr(func, '__qualname__', func), exc_info=True
            )
            continue
        if isinstance(extra, dict):
            out.update(extra)
    return out


def _compute_nav_badges(request) -> dict:
    """Per-request small counts that the sidebar surfaces as pills.

    Memoised on `request._morph_nav_badges` so the same context_processor
    triggered twice in one request (rare, but possible with included
    templates) doesn't re-query. Fail-soft — any plugin missing or
    DB error returns 0.
    """
    cached = getattr(request, '_morph_nav_badges', None)
    if cached is not None:
        return cached
    badges = {'returns': 0, 'insights': 0, 'notifications': 0}
    from plugins.registry import app_registry

    # Each count belongs to an app; a disabled app's badge stays at 0 (a
    # try/except guards an app's absence, not its being switched off).
    try:
        if app_registry.is_active('orders'):
            from plugins.installed.orders.refunds import ReturnRequest

            badges['returns'] = ReturnRequest.objects.filter(state='requested').count()
    except Exception:  # noqa: BLE001, S110
        pass
    try:
        if app_registry.is_active('ai_assistant'):
            from plugins.installed.ai_assistant.models import MerchantInsight

            badges['insights'] = MerchantInsight.objects.filter(is_read=False).count()
    except Exception:  # noqa: BLE001, S110
        pass
    try:
        if app_registry.is_active('notifications_center'):
            from plugins.installed.notifications_center.services import unread_count_for

            badges['notifications'] = unread_count_for(getattr(request, 'user', None))
    except Exception:  # noqa: BLE001, S110
        pass
    try:  # noqa: SIM105
        request._morph_nav_badges = badges
    except Exception:  # noqa: BLE001, S110
        pass
    return badges
