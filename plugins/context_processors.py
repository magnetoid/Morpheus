"""Plugin context processor — exposes active plugins + dashboard contributions."""

from __future__ import annotations

from collections import OrderedDict

# Section display order in the admin sidebar — Shopify-style top-to-bottom.
# Sections not in this list fall through to alphabetical order at the bottom.
_SECTION_ORDER = [
    # Main sidebar — contributed sections render below the hardcoded
    # Home / Linda / Orders / Products / Customers entries, in this order.
    # Target IA: docs/plans/dashboard-ia-redesign-2026-06.md.
    'catalog',  # Stockout forecast, Book taxonomies — sits nearest Products
    'customers',  # CRM (Leads, Accounts, Deals, Tasks), Subscriptions
    'cms',  # Pages, Blocks, Menus, Forms, Media assets
    'marketing',  # Campaigns, Promotions, Coupons, Gift cards
    'seo',  # SEO audit, redirects, JSON-LD config (7 pages — own section)
    'growth',  # Affiliates (list, programs, links, conversions, payouts)
    'analytics',  # Sessions, Events, Funnels
    'ai',  # Agent setup beyond the hardcoded Linda group
    'marketplace',  # Vendor onboarding, splits, payouts
    'plugins',  # uncategorised main-nav plugin pages
    # Settings sidebar (admin / setup)
    'developer',  # Webhooks endpoints + deliveries
    'access',  # Roles & users (RBAC)
    'data',  # Bulk CSV import/export, Demo data
    'settings',  # legacy 'settings' bucket — anything left over
    'apps',  # the Apps catalog page
]

_SECTION_LABELS = {
    'ai': 'AI & agents',
    'sales': 'Sales',
    'catalog': 'Catalog',
    'customers': 'Customers',
    'marketing': 'Marketing',
    'cms': 'Content',
    'analytics': 'Analytics',
    'seo': 'SEO',
    'growth': 'Affiliates',
    'marketplace': 'Multivendor',
    'plugins': 'More plugins',
    'developer': 'Developer tools',
    'access': 'Access & roles',
    'data': 'Data tools',
    'settings': 'Settings',
    'apps': 'Apps',
}


# Lucide icon for each known section. Falls through to 'folder' for
# anything not listed — matches the template default.
_SECTION_ICONS = {
    'ai': 'sparkles',
    'sales': 'shopping-cart',
    'catalog': 'package',
    'crm': 'users',
    'customers': 'users',
    'marketing': 'megaphone',
    'cms': 'book-open',
    'analytics': 'bar-chart-3',
    'seo': 'search',
    'growth': 'trending-up',
    'marketplace': 'store',
    'plugins': 'puzzle',
    'developer': 'terminal',
    'access': 'shield',
    'data': 'database',
    'settings': 'settings',
    'apps': 'grid-3x3',
}


def _group_by_section(pages, *, active_apps_slug: str = ''):
    """Group + order pages by section the same way for any sidebar.

    ``active_apps_slug`` is the current `plugin/slug` (computed elsewhere
    in this module) — when supplied, the matching section is marked
    ``is_active=True`` so the template can pre-expand it.
    """
    by_section: dict[str, list] = {}
    for page in pages:
        by_section.setdefault(page.section or 'plugins', []).append(page)

    grouped: OrderedDict[str, list] = OrderedDict()
    for key in _SECTION_ORDER:
        if key in by_section:
            grouped[key] = by_section.pop(key)
    for key in sorted(by_section.keys()):
        grouped[key] = by_section[key]

    out = []
    for key, pages_in_section in grouped.items():
        is_active = False
        if active_apps_slug:
            for p in pages_in_section:
                if f'{p.plugin}/{p.slug}' == active_apps_slug:
                    is_active = True
                    break
        out.append(
            {
                'key': key,
                'label': _SECTION_LABELS.get(key, key.replace('_', ' ').title()),
                'icon': _SECTION_ICONS.get(key, 'folder'),
                'pages': pages_in_section,
                'is_active': is_active,
            }
        )
    return out


def plugin_context(request):
    from plugins.registry import plugin_registry

    pages = plugin_registry.dashboard_pages()

    # Split by sidebar destination.
    # The 'apps' section is the catch-all bucket for plugins that
    # haven't categorised themselves. Render the bucket in the
    # *settings* sidebar (where the explicit "Apps" link already
    # lives) rather than at the bottom of the main rail — keeps the
    # daily-use sidebar focused.
    main_pages = [
        p
        for p in pages
        if getattr(p, 'nav', 'main') not in ('settings', 'hidden')
        and getattr(p, 'section', '') not in ('apps', 'products')
    ]
    # Pages that declare section='products' render as children of the hardcoded
    # "Products" nav group (just below Collections), ordered by `order` — so a
    # plugin owns where its entry lands under Products (ADR 0016) instead of a
    # hardcoded link in admin_dashboard's base.html.
    products_nav_children = [
        {
            'label': p.label,
            'url': getattr(p, 'url', '') or f'/dashboard/apps/{p.plugin}/{p.slug}/',
            'is_active': request.path.startswith(
                getattr(p, 'url', '') or f'/dashboard/apps/{p.plugin}/{p.slug}/'
            ),
        }
        for p in sorted(
            (
                p
                for p in pages
                if getattr(p, 'nav', 'main') == 'main' and getattr(p, 'section', '') == 'products'
            ),
            key=lambda p: getattr(p, 'order', 100),
        )
    ]
    settings_pages = [
        p
        for p in pages
        if (
            getattr(p, 'nav', 'main') == 'settings'
            or (getattr(p, 'nav', 'main') == 'main' and getattr(p, 'section', '') == 'apps')
        )
        # Developer tools render as cards inside the Developers hub
        # (/dashboard/settings/developer/), not as individual sidebar
        # entries — one "Developer" link instead of seven.
        and getattr(p, 'section', '') != 'developer'
    ]

    # Shopify-style settings categories — drives the settings sidebar.
    # Only show categories that actually have at least one panel inside
    # (or 'general' / 'apps' which always make sense to expose).
    try:
        from plugins.installed.admin_dashboard.settings_categories import (
            SETTINGS_CATEGORIES,
        )

        panels_by_cat: dict[str, int] = {}
        for entry in plugin_registry.all_settings_panels():
            panel = (
                entry.get('panel')
                if isinstance(entry, dict)
                else entry[1]
                if isinstance(entry, tuple)
                else entry
            )
            cat = getattr(panel, 'category', '') or 'apps'
            panels_by_cat[cat] = panels_by_cat.get(cat, 0) + 1
        # Domains whose settings live on a dedicated rich page (Tax, Shipping)
        # are suppressed here so the settings sidebar shows ONE entry per domain
        # — the page itself (in settings_sections), never also a duplicate
        # category link. Their panels (carrier creds, Bookvault, …) stay
        # reachable via the settings hub. ADR 0004; the full "absorb the panels
        # onto the page" step is the remaining follow-up.
        _page_owned = {'shipping', 'taxes'}
        settings_category_nav = [
            c
            for c in SETTINGS_CATEGORIES
            # 'general', 'apps', 'notifications' always render: 'general'
            # carries store basics, 'apps' is the long-tail bucket, and
            # 'notifications' carries the editable email templates link
            # (which lives in the template, not a SettingsPanel).
            if (panels_by_cat.get(c.slug) or c.slug in ('general', 'apps', 'notifications'))
            and c.slug not in _page_owned
        ]
    except Exception:  # noqa: BLE001 — never fail the page on missing module
        settings_category_nav = []

    nav_badges = _compute_nav_badges(request)
    active_apps_slug = ''
    active_settings_category = ''

    # Derive active-state slugs from `request.path` so the settings sidebar
    # can highlight the right entry without every view setting context vars.
    #   /dashboard/settings/                      → active_settings_category=''
    #   /dashboard/settings/<category>/[...]      → active_settings_category=<category>
    #   /dashboard/settings/email-templates/[...] → active_settings_category='notifications'
    #     (email templates live under the 'notifications' category visually)
    #   /dashboard/apps/<plugin>/settings/        → active_apps_slug='<plugin>/settings'
    #   /dashboard/apps/<plugin>/<slug>/          → active_apps_slug='<plugin>/<slug>'
    path = getattr(request, 'path', '') or ''
    if path.startswith('/dashboard/settings/'):
        rest = path[len('/dashboard/settings/') :].strip('/').split('/', 1)
        head = rest[0] if rest and rest[0] else ''
        if head == 'email-templates':  # noqa: SIM108
            active_settings_category = 'notifications'
        else:
            active_settings_category = head
    elif path.startswith('/dashboard/apps/'):
        rest = path[len('/dashboard/apps/') :].strip('/').split('/')
        if len(rest) >= 2 and rest[0]:
            active_apps_slug = f'{rest[0]}/{rest[1]}'

    return {
        'active_plugins': plugin_registry._active,
        'plugin_registry': plugin_registry,
        'nav_badges': nav_badges,
        'dashboard_pages': pages,  # back-compat flat list
        'sidebar_sections': _group_by_section(main_pages, active_apps_slug=active_apps_slug),
        # Plugin pages that opt into the hardcoded "Products" nav group.
        'products_nav_children': products_nav_children,
        'settings_sections': _group_by_section(settings_pages, active_apps_slug=active_apps_slug),
        # Schema-driven settings panels (form-based).
        'plugin_settings_panels': plugin_registry.all_settings_panels(),
        # Settings categories shown in the settings-mode sidebar.
        'settings_category_nav': settings_category_nav,
        # Per-page active slugs the sidebar template uses to mark the right
        # link active when the user is inside a settings category or a
        # plugin-contributed dashboard page.
        'active_settings_category': active_settings_category,
        'active_apps_slug': active_apps_slug,
    }


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
    try:
        from plugins.installed.orders.refunds import ReturnRequest

        badges['returns'] = ReturnRequest.objects.filter(state='requested').count()
    except Exception:  # noqa: BLE001, S110
        pass
    try:
        from plugins.installed.ai_assistant.models import MerchantInsight

        badges['insights'] = MerchantInsight.objects.filter(is_read=False).count()
    except Exception:  # noqa: BLE001, S110
        pass
    try:
        from plugins.installed.notifications_center.services import unread_count_for

        badges['notifications'] = unread_count_for(getattr(request, 'user', None))
    except Exception:  # noqa: BLE001, S110
        pass
    try:  # noqa: SIM105
        request._morph_nav_badges = badges
    except Exception:  # noqa: BLE001, S110
        pass
    return badges
