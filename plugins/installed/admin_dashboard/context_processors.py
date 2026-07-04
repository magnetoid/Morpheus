"""Dashboard breadcrumbs — a path-derived fallback trail for every
/dashboard/ page, so a page gets a breadcrumb even when its view doesn't
supply an explicit `breadcrumb_trail`. Views that DO set `breadcrumb_trail`
win (base.html prefers it over `auto_breadcrumb_trail`).
"""

from __future__ import annotations

import re

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
    'apps': 'Apps',
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


def dashboard_breadcrumbs(request) -> dict:
    path = getattr(request, 'path', '') or ''
    if not path.startswith('/dashboard/'):
        return {}
    try:
        rest = path[len('/dashboard/') :].strip('/')
        trail = [{'label': 'Dashboard', 'url': '/dashboard/'}]
        acc = '/dashboard/'
        segs = [s for s in rest.split('/') if s]
        # Keep meaningful segments; drop record-id segments from the labels
        # but still advance the URL so links stay correct.
        kept = [(s, not _ID_RE.match(s)) for s in segs]
        visible = [s for s, show in kept if show]
        for seg, show in kept:
            acc = acc + seg + '/'
            if not show:
                continue
            is_last_visible = seg == visible[-1] if visible else False
            trail.append(
                {'label': _label(seg)} if is_last_visible else {'label': _label(seg), 'url': acc}
            )
        # A bare /dashboard/ (home) needs no breadcrumb.
        return {'auto_breadcrumb_trail': trail if len(trail) > 1 else []}
    except Exception:  # noqa: BLE001 — breadcrumbs must never break a render
        return {}
