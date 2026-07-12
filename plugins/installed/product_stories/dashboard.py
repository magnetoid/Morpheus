"""Dashboard editor for product story blocks (under Catalog)."""

from __future__ import annotations

import contextlib

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from plugins.installed.admin_dashboard.breadcrumbs import build_trail

_FIELDS = ('eyebrow', 'heading', 'body', 'image_url', 'layout')


def _trail(*items):
    return build_trail('Product stories', '/dashboard/stories/', *items)


@staff_member_required
def stories_index(request):
    from plugins.installed.catalog.models import Product
    from plugins.installed.product_stories.models import ProductStoryBlock

    if request.method == 'POST':
        slug = (request.POST.get('slug') or '').strip()
        if Product.objects.filter(slug=slug).exists():
            return redirect(f'/dashboard/stories/{slug}/')
        messages.error(request, f'No product with slug “{slug}”.')
        return redirect('/dashboard/stories/')

    rows = (
        ProductStoryBlock.objects.values('product__slug', 'product__name')
        .annotate(n=Count('id'))
        .order_by('product__name')
    )
    return render(
        request,
        'product_stories/dashboard/index.html',
        {'rows': rows, 'active_nav': 'catalog', 'breadcrumb_trail': _trail()},
    )


@staff_member_required
def stories_product(request, slug):
    from plugins.installed.catalog.models import Product
    from plugins.installed.product_stories.models import ProductStoryBlock

    product = get_object_or_404(Product, slug=slug)

    if request.method == 'POST':
        action = request.POST.get('action') or 'create'
        if action == 'create':
            heading = (request.POST.get('heading') or '').strip()
            if heading:
                nxt = ProductStoryBlock.objects.filter(product=product).count()
                ProductStoryBlock.objects.create(
                    product=product,
                    order=nxt,
                    heading=heading[:200],
                    eyebrow=(request.POST.get('eyebrow') or '').strip()[:60],
                    body=(request.POST.get('body') or '').strip(),
                    image_url=(request.POST.get('image_url') or '').strip()[:500],
                    layout=(request.POST.get('layout') or 'image_right'),
                )
                messages.success(request, 'Story block added.')
        else:
            block = ProductStoryBlock.objects.filter(
                id=request.POST.get('block_id'), product=product
            ).first()
            if block and action == 'update':
                for f in _FIELDS:
                    if f in request.POST:
                        setattr(block, f, request.POST[f].strip())
                with contextlib.suppress(TypeError, ValueError):
                    block.order = max(0, int(request.POST.get('order') or block.order))
                block.is_active = request.POST.get('is_active') == 'on'
                block.save()
                messages.success(request, 'Story block saved.')
            elif block and action == 'delete':
                block.delete()
                messages.success(request, 'Story block deleted.')
        return redirect(f'/dashboard/stories/{slug}/')

    blocks = ProductStoryBlock.objects.filter(product=product).order_by('order', 'created_at')
    return render(
        request,
        'product_stories/dashboard/product.html',
        {
            'product': product,
            'blocks': blocks,
            'LAYOUTS': ProductStoryBlock.LAYOUT_CHOICES,
            'active_nav': 'catalog',
            'breadcrumb_trail': _trail({'label': product.name}),
        },
    )
