"""Collection CRUD for the admin dashboard (catalog.Collection).

List + create + edit + delete of merchant collections — the curated
``/collection/<slug>/`` storefront pages (and the homepage featured rails).
Lives under the Products nav group. Unlike categories (read-only for now),
collections get full create/edit here since there's no Django admin for them.
"""

# ruff: noqa: PLC0415, I001
# Inline imports match the views_split convention (avoid app-load-order deps).

from __future__ import annotations

from morpheus.app.views import (
    HttpRequest,
    HttpResponse,
    messages,
    redirect,
    render,
    staff_member_required,
)

from plugins.installed.admin_dashboard.views_split._shared import logger


def _breadcrumb(tail: str) -> list[dict]:
    return [
        {'label': 'Dashboard', 'url': '/dashboard/'},
        {'label': 'Products', 'url': '/dashboard/products/'},
        {'label': 'Collections', 'url': '/dashboard/collections/'},
        {'label': tail},
    ]


@staff_member_required
def collections_list(request: HttpRequest) -> HttpResponse:
    from django.db.models import Count

    from plugins.installed.catalog.models import Collection

    search = (request.GET.get('q') or '').strip()[:80]
    qs = Collection.objects.all().annotate(product_count=Count('products'))
    if search:
        qs = qs.filter(name__icontains=search)
    qs = qs.order_by('sort_order', 'name')
    return render(
        request,
        'admin_dashboard/collections.html',
        {
            'collections': qs,
            'search': search,
            'active_nav': 'collections',
            'breadcrumb_trail': _breadcrumb('Collections')[:3],
        },
    )


@staff_member_required
def collection_new(request: HttpRequest) -> HttpResponse:
    from plugins.installed.admin_dashboard.forms.collections import CollectionForm

    if request.method == 'POST':
        form = CollectionForm(request.POST, files=request.FILES)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f'Collection “{obj.name}” created.')
            return redirect('admin_dashboard:collection_edit', collection_id=obj.id)
    else:
        form = CollectionForm()
    return render(
        request,
        'admin_dashboard/collection_form.html',
        {
            'form': form,
            'is_new': True,
            'active_nav': 'collections',
            'breadcrumb_trail': _breadcrumb('New collection'),
        },
    )


@staff_member_required
def collection_edit(request: HttpRequest, collection_id: str) -> HttpResponse:
    from django.shortcuts import get_object_or_404

    from plugins.installed.admin_dashboard.forms.collections import CollectionForm
    from plugins.installed.catalog.models import Collection

    collection = get_object_or_404(Collection, pk=collection_id)
    if request.method == 'POST':
        form = CollectionForm(request.POST, files=request.FILES, instance=collection)
        if form.is_valid():
            form.save()
            messages.success(request, 'Collection saved.')
            return redirect('admin_dashboard:collection_edit', collection_id=collection.id)
    else:
        form = CollectionForm(instance=collection)
    return render(
        request,
        'admin_dashboard/collection_form.html',
        {
            'form': form,
            'collection': collection,
            'is_new': False,
            'active_nav': 'collections',
            'breadcrumb_trail': _breadcrumb(collection.name[:50]),
        },
    )


@staff_member_required
def collection_delete(request: HttpRequest, collection_id: str) -> HttpResponse:
    from plugins.installed.catalog.models import Collection

    if request.method != 'POST':
        return redirect('admin_dashboard:collections')
    try:
        Collection.objects.filter(pk=collection_id).delete()
        messages.success(request, 'Collection deleted.')
    except Exception as e:  # noqa: BLE001
        logger.warning('collection_delete failed: %s', e, exc_info=True)
        messages.error(request, 'Could not delete that collection.')
    return redirect('admin_dashboard:collections')
