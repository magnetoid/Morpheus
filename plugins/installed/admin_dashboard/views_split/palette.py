"""Cmd+K command palette — a wide, cross-app search backing the header search.

Returns hits grouped into ordered `section`s: every dashboard page (pulled
from the DashboardPage registry, so the palette covers the *whole* app —
not a hand-maintained list), plus live entity matches across the commerce
spine and catalog/content, plus a "search the storefront" escape hatch.

Each hit carries `section` (the group title, in the order the front-end
should render), `kind`, `label`, `hint`, `url`, `icon`. Every plugin lookup
is fail-soft — a disabled or absent plugin simply contributes nothing.
"""

from __future__ import annotations

from morpheus.plugin.views import (
    HttpRequest,
    HttpResponse,
    staff_member_required,
)

# High-value create/jump actions that aren't registered DashboardPages.
_ACTIONS = [
    ('Home', 'Dashboard overview', '/dashboard/', 'home'),
    ('New order', 'Create a draft order', '/dashboard/orders/new/', 'plus'),
    ('New product', 'Create a product', '/dashboard/products/new/', 'plus'),
    ('New customer', 'Create a customer', '/dashboard/customers/new/', 'plus'),
    ('All orders', 'Open the orders list', '/dashboard/orders/', 'shopping-bag'),
    ('All products', 'Open the products list', '/dashboard/products/', 'package'),
    ('Customers', 'Open the customers list', '/dashboard/customers/', 'users'),
    ('Settings', 'Store configuration', '/dashboard/settings/', 'settings'),
]


def _nav_hits(q: str, ql: str) -> list[dict]:
    """Every dashboard page (registry) + core actions, filtered by query."""
    hits: list[dict] = []
    seen: set[str] = set()

    def add(label, hint, url, icon):
        if url in seen:
            return
        if q and ql not in label.lower() and ql not in (hint or '').lower():
            return
        seen.add(url)
        hits.append(
            {
                'section': 'Go to',
                'kind': 'nav',
                'label': label,
                'hint': hint,
                'url': url,
                'icon': icon,
            }
        )

    for label, hint, url, icon in _ACTIONS:
        add(label, hint, url, icon)

    try:
        from plugins.context_processors import _SECTION_LABELS  # noqa: PLC0415
        from plugins.registry import plugin_registry  # noqa: PLC0415

        for page in plugin_registry.dashboard_pages():
            if getattr(page, 'nav', 'main') == 'hidden':
                continue
            url = getattr(page, 'url', '') or (
                f'/dashboard/apps/{getattr(page, "plugin", "")}/{page.slug}/'
            )
            section = _SECTION_LABELS.get(getattr(page, 'section', ''), '')
            add(page.label, section or 'Dashboard', url, getattr(page, 'icon', 'circle'))
    except Exception:  # noqa: BLE001, S110
        pass
    return hits


def _entity_hits(q: str) -> list[dict]:
    """Live matches across the commerce spine + catalog + content. Fail-soft."""
    from django.contrib.auth import get_user_model  # noqa: PLC0415
    from django.db.models import Q  # noqa: PLC0415

    hits: list[dict] = []

    try:
        from plugins.installed.orders.models import Order  # noqa: PLC0415

        for o in Order.objects.filter(
            Q(order_number__icontains=q) | Q(email__icontains=q)
        ).order_by('-placed_at')[:5]:
            hits.append(
                {
                    'section': 'Orders',
                    'kind': 'order',
                    'label': f'#{o.order_number}',
                    'hint': f'{o.email or "—"} · {o.get_status_display()}',
                    'url': f'/dashboard/orders/{o.order_number}/',
                    'icon': 'shopping-bag',
                }
            )
    except Exception:  # noqa: BLE001, S110
        pass

    try:
        from plugins.installed.catalog.models import Product  # noqa: PLC0415

        for p in Product.objects.filter(Q(name__icontains=q) | Q(sku__icontains=q))[:6]:
            hits.append(
                {
                    'section': 'Products',
                    'kind': 'product',
                    'label': p.name,
                    'hint': p.sku or '—',
                    'url': f'/dashboard/products/{p.id}/',
                    'icon': 'package',
                }
            )
    except Exception:  # noqa: BLE001, S110
        pass

    try:
        User = get_user_model()  # noqa: N806
        for u in User.objects.filter(
            Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )[:5]:
            name = (f'{getattr(u, "first_name", "")} {getattr(u, "last_name", "")}').strip()
            hits.append(
                {
                    'section': 'Customers',
                    'kind': 'customer',
                    'label': name or u.email,
                    'hint': u.email if name else '—',
                    'url': f'/dashboard/customers/{u.id}/',
                    'icon': 'user',
                }
            )
    except Exception:  # noqa: BLE001, S110
        pass

    try:
        from plugins.installed.catalog.models import Category  # noqa: PLC0415

        for c in Category.objects.filter(name__icontains=q)[:4]:
            hits.append(
                {
                    'section': 'Categories',
                    'kind': 'category',
                    'label': c.name,
                    'hint': 'Category',
                    'url': f'/dashboard/categories/{c.id}/edit/',
                    'icon': 'folder',
                }
            )
    except Exception:  # noqa: BLE001, S110
        pass

    try:
        from plugins.installed.catalog.models import Collection  # noqa: PLC0415

        for c in Collection.objects.filter(name__icontains=q)[:4]:
            hits.append(
                {
                    'section': 'Collections',
                    'kind': 'collection',
                    'label': c.name,
                    'hint': 'Collection',
                    'url': f'/dashboard/collections/{c.id}/edit/',
                    'icon': 'layers',
                }
            )
    except Exception:  # noqa: BLE001, S110
        pass

    try:
        from plugins.installed.cms.models import Page  # noqa: PLC0415

        for pg in Page.objects.filter(title__icontains=q)[:4]:
            hits.append(
                {
                    'section': 'Content',
                    'kind': 'page',
                    'label': pg.title,
                    'hint': f'/{pg.slug}',
                    'url': f'/dashboard/cms/pages/{pg.id}/edit/',
                    'icon': 'file-text',
                }
            )
    except Exception:  # noqa: BLE001, S110
        pass

    return hits


@staff_member_required
def palette_search(request: HttpRequest) -> HttpResponse:
    """JSON endpoint backing the Cmd+K palette. See module docstring."""
    from django.http import JsonResponse  # noqa: PLC0415

    q = (request.GET.get('q') or '').strip()
    ql = q.lower()

    nav = _nav_hits(q, ql)
    if not q:
        return JsonResponse({'hits': nav[:12]})

    hits = nav[:6] + _entity_hits(q)
    # Always offer a storefront search escape hatch for the raw query.
    hits.append(
        {
            'section': 'Storefront',
            'kind': 'shop',
            'label': f'Search the shop for “{q}”',
            'hint': 'Open the storefront search',
            'url': f'/products/?q={q}',
            'icon': 'store',
        }
    )
    return JsonResponse({'hits': hits[:40]})
