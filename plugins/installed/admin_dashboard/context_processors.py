"""Dashboard shell context: navigation, breadcrumbs and contributed chrome.

`dashboard_nav` hands the templates the sidebar sections, the current
section's tabs and the settings categories (see `navigation.py`). It runs
for dashboard requests only, so the storefront never pays for it.

The breadcrumb is a fallback trail for every /dashboard/ page that doesn't
supply an explicit `breadcrumb_trail` (base.html prefers the explicit one),
and base.html shows it only below a tab — on a tab's own page the tab strip
already says where you are. The trail follows the page's place in the
navigation, not the URL path: `Dashboard › <Section> › <Tab> › …`, so it
never leaks the internal `/dashboard/apps/` discovery prefix. Pages the
navigation doesn't know fall back to a path-derived trail with `apps`
stripped.
"""

from __future__ import annotations

import logging
import re

from django.conf import settings

logger = logging.getLogger('morpheus.admin')

# Slugs that should render as a fixed pretty label (acronyms + known pages).
_LABELS = {
    'ai': 'AI',
    'ai-insights': 'AI insights',
    'seo': 'SEO',
    'cms': 'CMS',
    'api': 'API',
    'mcp': 'MCP',
    'rbac': 'Roles & users',
    'b2b': 'B2B',
    'pwa': 'PWA',
    'ui': 'UI',
    'crm': 'CRM',
    'kpis': 'KPIs',
    'agents': 'Agents',
    'settings': 'Settings',
    'products': 'Products',
    'orders': 'Orders',
    'customers': 'Users',
    'analytics': 'Analytics',
    'draft-orders': 'Draft orders',
    'gift-cards': 'Gift cards',
}

# Segments that are record ids (UUID / long hex / all-digits) — skip them so
# a detail URL reads "Products" not "Products > 3f0c…-…".
_ID_RE = re.compile(r'^([0-9a-f]{8,}|[0-9a-f-]{20,}|\d+)$', re.IGNORECASE)


def _label(slug: str) -> str:
    if slug in _LABELS:
        return _LABELS[slug]
    return slug.replace('-', ' ').replace('_', ' ').strip().capitalize()


def _section_crumbs(request, loc) -> list[dict]:
    from plugins.installed.admin_dashboard import navigation  # noqa: PLC0415

    sec = navigation.section(loc.section)
    listed = [
        t
        for t in navigation.tabs(getattr(request, 'user', None))
        if t.section == sec.key and t.nav == 'main'
    ]
    landing = sec.url or (listed[0].url if listed else loc.tab.url)
    crumbs = [{'label': sec.label, 'url': landing}]
    members = [t for t in listed if loc.tab.group and t.group == loc.tab.group]
    if len(members) > 1:
        crumbs.append({'label': loc.tab.group, 'url': members[0].url})
    if loc.tab.url != landing:
        crumbs.append({'label': loc.tab.label, 'url': loc.tab.url})
    return crumbs


def _settings_crumbs(loc) -> list[dict]:
    from plugins.installed.admin_dashboard.settings_categories import (  # noqa: PLC0415
        get_category,
    )

    crumbs = [{'label': 'Settings', 'url': '/dashboard/settings/'}]
    cat = get_category(loc.section) if loc.section else None
    if cat is not None:
        crumbs.append({'label': cat.label, 'url': f'/dashboard/settings/{cat.slug}/'})
    elif loc.section == 'apps-catalogue':
        crumbs.append({'label': 'Apps', 'url': '/dashboard/apps/'})
    if loc.tool is not None:
        crumbs.append({'label': loc.tool.label, 'url': loc.tool.url})
    return crumbs


def _nav_trail(request) -> list | None:
    """The breadcrumb for a page the navigation knows, or None.

    `Dashboard › <Section> › [<Group>] › <Tab> › <sub-path…>`, where the
    section's own landing tab is not repeated ("Dashboard › Products", not
    "… › Products › All products") and a label equal to the one before it is
    dropped ("Marketing › Affiliates", not "… › Affiliates › Affiliates").
    Everything above the current page links back; record ids are skipped.
    """
    from plugins.installed.admin_dashboard import navigation  # noqa: PLC0415

    loc = navigation.build(request)['location']
    if loc.mode == 'main' and loc.tab is not None:
        crumbs = _section_crumbs(request, loc)
    elif loc.mode == 'settings':
        crumbs = _settings_crumbs(loc)
    else:
        return None
    crumbs += [{'label': _label(seg)} for seg in loc.leftover if not _ID_RE.match(seg)]

    trail = [{'label': 'Dashboard', 'url': '/dashboard/'}]
    for crumb in crumbs:
        if crumb['label'].strip().casefold() == trail[-1]['label'].strip().casefold():
            trail[-1] = crumb  # "Affiliates › Affiliates" → one crumb
            continue
        trail.append(crumb)
    # The page you are on is a label, not a link.
    if len(trail) > 1 and request.path == trail[-1].get('url', request.path):
        trail[-1] = {'label': trail[-1]['label']}
    return trail


def _path_trail(path: str) -> list:
    """Path-derived fallback for pages with no registered nav entry (core
    sections, unmatched detail routes). Strips the internal `apps` prefix so
    it never leaks into the trail."""
    rest = path[len('/dashboard/') :].strip('/')
    trail = [{'label': 'Dashboard', 'url': '/dashboard/'}]
    acc = '/dashboard/'
    segs = [s for s in rest.split('/') if s]
    kept = [(s, not _ID_RE.match(s) and s != 'apps') for s in segs]
    visible = [s for s, show in kept if show]
    for seg, show in kept:
        acc = acc + seg + '/'
        if not show:
            continue
        is_last_visible = seg == visible[-1] if visible else False
        trail.append(
            {'label': _label(seg)} if is_last_visible else {'label': _label(seg), 'url': acc}
        )
    return trail


def dashboard_breadcrumbs(request) -> dict:
    path = getattr(request, 'path', '') or ''
    if not path.startswith('/dashboard/'):
        return {}
    try:
        trail = _nav_trail(request) or _path_trail(path)
        # A bare /dashboard/ (home) needs no breadcrumb.
        return {'auto_breadcrumb_trail': trail if len(trail) > 1 else []}
    except Exception:  # noqa: BLE001 — breadcrumbs must never break a render
        logger.warning('dashboard breadcrumb failed for %s', path, exc_info=True)
        return {}


def dashboard_nav(request) -> dict:
    """The sidebar sections, the current section's tabs and the settings
    categories (navigation.py), plus the nav badges. Dashboard requests only.

    A failure here empties the sidebar, so it is loud where someone is
    looking: re-raised under tests and DEBUG, logged at ERROR in production
    (the page still renders, with the Settings link)."""
    path = getattr(request, 'path', '') or ''
    if not path.startswith('/dashboard/'):
        return {}
    try:
        from plugins.installed.admin_dashboard import navigation  # noqa: PLC0415

        nav = navigation.build(request)
    except Exception:
        if settings.DEBUG or getattr(settings, '_RUNNING_TESTS', False):
            raise
        logger.error('dashboard navigation failed for %s', path, exc_info=True)
        return {}
    return {'dashboard_nav': nav, 'nav_badges': nav['badges']}


def dashboard_shell(request) -> dict:
    """Contributed shell surfaces: account-dropdown items and body-end templates.

    The shell must not hardcode a link to an optional app (ADR 0023) — it fires,
    apps answer, and the hook bus drops handlers whose plugin is inactive, so a
    contributed item disappears on disable for free. Fail-soft in both
    directions: a broken subscriber must never take out every dashboard page.
    """
    path = getattr(request, 'path', '') or ''
    if not path.startswith('/dashboard/'):
        return {}
    try:
        from morpheus.core import MorpheusEvents, hook_registry  # noqa: PLC0415

        items = hook_registry.filter(MorpheusEvents.DASHBOARD_USER_MENU, value=[], request=request)
        items = [i for i in (items or []) if isinstance(i, dict) and i.get('label')]
        items.sort(key=lambda i: i.get('order', 100))
        body_end = hook_registry.filter(
            MorpheusEvents.DASHBOARD_BODY_END, value=[], request=request
        )
        body_end = [t for t in (body_end or []) if isinstance(t, str) and t]
        return {'dashboard_user_menu': items, 'dashboard_body_end': body_end}
    except Exception:  # noqa: BLE001 — a bad subscriber must not 500 the shell
        return {}
