"""Plugin context processor — exposes active plugins + dashboard contributions."""
from __future__ import annotations

from collections import OrderedDict


# Section display order in the admin sidebar — Shopify-style top-to-bottom.
# Sections not in this list fall through to alphabetical order at the bottom.
_SECTION_ORDER = [
    # Main sidebar (daily-use)
    'ai',           # AI & agents — Morpheus's defining surface; goes at the top
    'sales',        # Orders (drafts surface inline)
    'catalog',      # Products, Categories, Collections
    'crm',          # Leads, Accounts, Deals, Tasks
    'marketing',    # Campaigns, Promotions, Coupons
    'cms',          # Pages, Blocks, Menus, Forms
    'analytics',    # Sessions, Events, Funnels
    'seo',          # SEO audit, redirects, JSON-LD config
    'growth',       # Affiliates, loyalty
    'marketplace',  # Vendor onboarding, splits, payouts
    'plugins',      # uncategorised main-nav plugin pages

    # Settings sidebar (admin / setup)
    'developer',    # Webhooks endpoints + deliveries
    'access',       # Roles & users (RBAC)
    'data',         # Bulk CSV import/export, Demo data
    'settings',     # legacy 'settings' bucket — anything left over
    'apps',         # the Apps catalog page
]

_SECTION_LABELS = {
    'ai': 'AI & agents',
    'sales': 'Sales',
    'catalog': 'Catalog',
    'crm': 'Customers & CRM',
    'marketing': 'Marketing',
    'cms': 'Content',
    'analytics': 'Analytics',
    'seo': 'SEO',
    'growth': 'Growth',
    'marketplace': 'Marketplace',
    'plugins': 'More plugins',
    'developer': 'Developer tools',
    'access': 'Access & roles',
    'data': 'Data tools',
    'settings': 'Settings',
    'apps': 'Apps',
}


def _group_by_section(pages):
    """Group + order pages by section the same way for any sidebar."""
    by_section: dict[str, list] = {}
    for page in pages:
        by_section.setdefault(page.section or 'plugins', []).append(page)

    grouped: OrderedDict[str, list] = OrderedDict()
    for key in _SECTION_ORDER:
        if key in by_section:
            grouped[key] = by_section.pop(key)
    for key in sorted(by_section.keys()):
        grouped[key] = by_section[key]

    return [
        {
            'key': key,
            'label': _SECTION_LABELS.get(key, key.replace('_', ' ').title()),
            'pages': pages_in_section,
        }
        for key, pages_in_section in grouped.items()
    ]


def plugin_context(request):
    from plugins.registry import plugin_registry

    pages = plugin_registry.dashboard_pages()

    # Split by sidebar destination.
    main_pages = [p for p in pages if getattr(p, 'nav', 'main') != 'settings']
    settings_pages = [p for p in pages if getattr(p, 'nav', 'main') == 'settings']

    # Shopify-style settings categories — drives the settings sidebar.
    # Only show categories that actually have at least one panel inside
    # (or 'general' / 'apps' which always make sense to expose).
    try:
        from plugins.installed.admin_dashboard.settings_categories import (
            SETTINGS_CATEGORIES,
        )
        panels_by_cat: dict[str, int] = {}
        for entry in plugin_registry.all_settings_panels():
            panel = entry.get('panel') if isinstance(entry, dict) else entry[1] if isinstance(entry, tuple) else entry
            cat = getattr(panel, 'category', '') or 'apps'
            panels_by_cat[cat] = panels_by_cat.get(cat, 0) + 1
        settings_category_nav = [
            c for c in SETTINGS_CATEGORIES
            if panels_by_cat.get(c.slug) or c.slug in ('general', 'apps')
        ]
    except Exception:  # noqa: BLE001 — never fail the page on missing module
        settings_category_nav = []

    return {
        'active_plugins': plugin_registry._active,
        'plugin_registry': plugin_registry,
        'dashboard_pages': pages,                          # back-compat flat list
        'sidebar_sections': _group_by_section(main_pages),  # main sidebar
        'settings_sections': _group_by_section(settings_pages),  # settings sidebar
        # Schema-driven settings panels (form-based).
        'plugin_settings_panels': plugin_registry.all_settings_panels(),
        # Settings categories shown in the settings-mode sidebar.
        'settings_category_nav': settings_category_nav,
    }
