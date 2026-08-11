"""Dashboard breadcrumbs — a fallback trail for every /dashboard/ page, so a
page gets a breadcrumb even when its view doesn't supply an explicit
`breadcrumb_trail`. Views that DO set `breadcrumb_trail` win (base.html prefers
it over `auto_breadcrumb_trail`).

The trail follows the page's location in the dashboard NAV, not the URL path:
a plugin page declares a `DashboardPage(section=…, label=…)`, and the sidebar
groups it under that section. So the breadcrumb reads
`Dashboard › <Section> › <Page>` — matching where the entry sits in the
sidebar — instead of exposing the routing prefix (the old path-split trail
rendered `/dashboard/apps/marketplace/vendors/` as "Dashboard › Apps ›
Marketplace › Vendors", leaking the internal `apps` discovery router). Pages
with no registered nav entry (core sections at clean paths, register_urls
detail routes) fall back to a path-derived trail with `apps` stripped.
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


def _section_label(section: str) -> str:
    """Friendly name for a nav section key ('marketplace' → 'Multivendor'),
    reusing the same map the sidebar renders."""
    try:
        from plugins.context_processors import _SECTION_LABELS  # noqa: PLC0415

        return _SECTION_LABELS.get(section, section.replace('_', ' ').title())
    except Exception:  # noqa: BLE001
        return section.replace('_', ' ').title()


def _canonical_url(page) -> str:
    return getattr(page, 'url', '') or f'/dashboard/apps/{getattr(page, "plugin", "")}/{page.slug}/'


def _resolve_nav_page(path: str, pages):
    """Find the DashboardPage this path belongs to, plus the remaining
    (post-page) path segments. Returns (page, leftover_segments) or (None, []).

    Two shapes are matched:
      * `/dashboard/apps/<plugin>/<slug>/…` — the page's canonical URL is a
        prefix of the path (longest match wins; also covers `url=` overrides).
      * `/dashboard/<plugin>/<slug>/…` — a register_urls detail route whose
        first two segments name the owning plugin + a page slug (e.g. the
        vendor-detail page under the Vendors list).
    """
    # 1) canonical-URL prefix match
    best, best_len = None, 0
    for page in pages:
        canon = _canonical_url(page)
        if canon and path.startswith(canon) and len(canon) > best_len:
            best, best_len = page, len(canon)
    if best is not None:
        leftover = [s for s in path[best_len:].strip('/').split('/') if s]
        return best, leftover

    # 2) register_urls detail route: /dashboard/<plugin>/<slug>/…
    segs = [s for s in path[len('/dashboard/') :].strip('/').split('/') if s]
    if len(segs) >= 2:
        plugin_seg, slug_seg = segs[0], segs[1]
        for page in pages:
            if getattr(page, 'plugin', '') == plugin_seg and page.slug == slug_seg:
                return page, segs[2:]
    return None, []


def _nav_trail(path: str) -> list | None:
    """Nav-location breadcrumb for a registered dashboard page, or None."""
    from plugins.registry import app_registry  # noqa: PLC0415

    pages = app_registry.dashboard_pages()
    page, leftover = _resolve_nav_page(path, pages)
    if page is None:
        return None

    trail = [{'label': 'Dashboard', 'url': '/dashboard/'}]
    section_label = _section_label(getattr(page, 'section', '') or 'plugins')
    # The section is a sidebar group, not a page — an unlinked label. Skip it
    # when it just repeats the page label (a single-plugin section named after
    # its occupant, e.g. growth→"Affiliates"), so the trail doesn't read
    # "Affiliates › Affiliates".
    if section_label.strip().casefold() != page.label.strip().casefold():
        trail.append({'label': section_label})

    leaf_segs = [s for s in leftover if not _ID_RE.match(s)]
    # The page is the current leaf only when nothing follows it. If any
    # segment follows — a sub-tab OR a record id (a detail route) — the page
    # label links back to its list and the record is "below" it.
    page_is_leaf = not leftover
    trail.append(
        {'label': page.label}
        if page_is_leaf
        else {'label': page.label, 'url': _canonical_url(page)}
    )
    # Any remaining non-id segments (sub-tabs) become trailing leaves.
    for i, seg in enumerate(leaf_segs):
        trail.append({'label': _label(seg)} if i == len(leaf_segs) - 1 else {'label': _label(seg)})
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
        trail = _nav_trail(path) or _path_trail(path)
        # A bare /dashboard/ (home) needs no breadcrumb.
        return {'auto_breadcrumb_trail': trail if len(trail) > 1 else []}
    except Exception:  # noqa: BLE001 — breadcrumbs must never break a render
        return {}
