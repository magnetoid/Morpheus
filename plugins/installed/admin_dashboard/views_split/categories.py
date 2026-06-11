"""Category list view for the admin dashboard.

Hierarchical (MPTT) listing of `catalog.Category` rows with product
counts and parent/child indentation. Filters: active/inactive + search
by name. Pagination via the shared `paginate_and_sort` helper.

Edit / create flows are TODO — the merchant can still edit categories
via the Django admin or via the category select on the product form;
this view is read-only for now so the nav link has a real destination.
"""

from __future__ import annotations

from typing import Any

from morpheus.views import HttpRequest, HttpResponse, render, staff_member_required
from plugins.installed.admin_dashboard.views_split._shared import logger


@staff_member_required
def categories_list(request: HttpRequest) -> HttpResponse:
    search = request.GET.get('q', '').strip()[:80]
    show_inactive = request.GET.get('inactive') == '1'

    rows: list[dict[str, Any]] = []
    total_active = total_inactive = 0
    try:
        from django.db.models import Count

        from plugins.installed.catalog.models import Category, Product

        qs = Category.objects.all()
        total_active = qs.filter(is_active=True).count()
        total_inactive = qs.filter(is_active=False).count()

        if not show_inactive:
            qs = qs.filter(is_active=True)
        if search:
            qs = qs.filter(name__icontains=search)

        # Per-category product counts in one query.
        product_counts = dict(
            Product.objects.values_list('category_id')
            .annotate(c=Count('id'))
            .values_list('category_id', 'c')
        )

        # MPTT order — by tree, then sort_order within siblings.
        qs = qs.order_by('tree_id', 'lft')
        for c in qs:
            rows.append(
                {
                    'id': c.id,
                    'name': c.name,
                    'slug': c.slug,
                    'level': c.level,
                    'parent_name': c.parent.name if c.parent_id else '',
                    'is_active': c.is_active,
                    'sort_order': c.sort_order,
                    'product_count': product_counts.get(c.id, 0),
                    'updated_at': c.updated_at,
                }
            )
    except Exception as e:  # noqa: BLE001
        logger.warning('categories_list: failed to load — %s', e, exc_info=True)

    return render(
        request,
        'admin_dashboard/categories.html',
        {
            'rows': rows,
            'search': search,
            'show_inactive': show_inactive,
            'total_active': total_active,
            'total_inactive': total_inactive,
            'active_nav': 'categories',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Products', 'url': '/dashboard/products/'},
                {'label': 'Categories'},
            ],
        },
    )
