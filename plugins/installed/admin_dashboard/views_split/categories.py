"""Category list, create and edit views for the admin dashboard.

Hierarchical (MPTT) listing of `catalog.Category` rows with product
counts and parent/child indentation, plus a full edit form (mirroring
the collection-edit flow) so a merchant can change a category's name,
slug, parent, image and SEO without dropping to the Django admin.
"""

# ruff: noqa: PLC0415, I001
# Inline imports match the views_split convention (avoid app-load-order deps).

from __future__ import annotations

from typing import Any

from morpheus.app.views import (
    HttpRequest,
    HttpResponse,
    messages,
    redirect,
    render,
    staff_member_required,
)
from plugins.installed.admin_dashboard.views_split._shared import logger


from core.authz import require_capability


@staff_member_required
@require_capability('catalog.read')
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


@staff_member_required
@require_capability('catalog.write')
def category_new(request: HttpRequest) -> HttpResponse:
    """Create a category in the dashboard (the stock admin is not mounted live)."""
    from plugins.installed.admin_dashboard.forms.categories import CategoryForm

    from plugins.installed.admin_dashboard.views_split._shared import (
        entity_form_cards,
        fire_entity_form_saved,
    )

    if request.method == 'POST':
        form = CategoryForm(request.POST, files=request.FILES)
        if form.is_valid():
            category = form.save()
            fire_entity_form_saved('category', category, request)
            messages.success(request, f'Category “{category.name}” created.')
            return redirect('admin_dashboard:category_edit', category_id=category.id)
    else:
        form = CategoryForm()
    return render(
        request,
        'admin_dashboard/category_form.html',
        {
            'form': form,
            'category': None,
            'extra_cards': entity_form_cards('category', None, request),
            'is_new': True,
            'active_nav': 'categories',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Products', 'url': '/dashboard/products/'},
                {'label': 'Categories', 'url': '/dashboard/categories/'},
                {'label': 'New category'},
            ],
        },
    )


@staff_member_required
@require_capability('catalog.write')
def category_edit(request: HttpRequest, category_id: str) -> HttpResponse:
    from django.shortcuts import get_object_or_404

    from plugins.installed.admin_dashboard.forms.categories import CategoryForm
    from plugins.installed.catalog.models import Category

    from plugins.installed.admin_dashboard.views_split._shared import (
        entity_form_cards,
        fire_entity_form_saved,
    )

    category = get_object_or_404(Category, pk=category_id)
    if request.method == 'POST':
        form = CategoryForm(request.POST, files=request.FILES, instance=category)
        if form.is_valid():
            form.save()
            fire_entity_form_saved('category', category, request)
            messages.success(request, 'Category saved.')
            return redirect('admin_dashboard:category_edit', category_id=category.id)
    else:
        form = CategoryForm(instance=category)
    return render(
        request,
        'admin_dashboard/category_form.html',
        {
            'form': form,
            'category': category,
            'extra_cards': entity_form_cards('category', category, request),
            'is_new': False,
            'active_nav': 'categories',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Products', 'url': '/dashboard/products/'},
                {'label': 'Categories', 'url': '/dashboard/categories/'},
                {'label': category.name[:50]},
            ],
        },
    )


@staff_member_required
@require_capability('catalog.write')
def category_quick_create(request: HttpRequest) -> HttpResponse:
    """Create a category from the product form's category picker; JSON in, JSON out.

    Same validation as the full form (a parent that exists, a unique slug), so a
    category made here is indistinguishable from one made on the Categories page.
    A name that already exists under the same parent picks that category instead
    of minting a twin; the same name under another parent gets its own slug
    (`oils`, then `oils-2`).
    """
    from django.http import JsonResponse
    from django.utils.text import slugify

    from plugins.installed.admin_dashboard.forms.categories import CategoryForm
    from plugins.installed.catalog.models import Category

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required.'}, status=405)
    name = ' '.join((request.POST.get('name') or '').split())[:200]
    if not name:
        return JsonResponse({'ok': False, 'error': 'Give the category a name.'}, status=400)
    parent = (request.POST.get('parent') or '').strip()

    form = CategoryForm(
        {
            'name': name,
            'slug': '',
            'parent': parent,
            'description': '',
            'is_active': 'on',
            'sort_order': '0',
        }
    )
    form.is_valid()  # parent first: an unknown parent is an error, not a lookup miss
    if 'parent' in form.errors:
        return JsonResponse({'ok': False, 'error': str(form.errors['parent'][0])}, status=400)
    twin = Category.objects.filter(
        name__iexact=name, parent=form.cleaned_data.get('parent')
    ).first()
    if twin is not None:
        return JsonResponse(_picker_entry(twin, existing=True))

    base = slugify(name) or 'category'
    slug, n = base, 2
    while Category.objects.filter(slug=slug).exists():
        slug, n = f'{base}-{n}', n + 1
    form = CategoryForm({**form.data, 'slug': slug})
    if not form.is_valid():
        first = next(iter(form.errors.values()))[0] if form.errors else 'Invalid category.'
        return JsonResponse({'ok': False, 'error': str(first)}, status=400)
    return JsonResponse(_picker_entry(form.save(), existing=False))


def _picker_entry(category, *, existing: bool) -> dict:
    """What the category picker needs to place a category in its tree."""
    ancestors = list(category.get_ancestors()) if category.parent_id else []
    return {
        'ok': True,
        'existing': existing,
        'id': str(category.id),
        'name': category.name,
        'parent_id': str(category.parent_id) if category.parent_id else '',
        'depth': len(ancestors),
        'path': ' › '.join([*(a.name for a in ancestors), category.name]),
    }
