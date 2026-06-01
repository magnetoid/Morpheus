"""dynamic_products — dashboard config views (staff-only).

A small CRUD over :class:`DynamicBlock`: list, create/edit, delete. All
templates live under this plugin's own ``templates/dynamic_products/``;
nothing is hard-coded into admin_dashboard, so disabling the plugin takes
the whole settings page with it.
"""

# ruff: noqa: PLC0415 — inline imports match sibling dashboard views and
#       avoid import-time coupling to optional plugins (catalog/metafields).

from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render

from .models import (
    SLOT_CHOICES,
    STRATEGY_CHOICES,
    DynamicBlock,
)


def _trail(*items):
    trail = [
        {'label': 'Dashboard', 'url': '/dashboard/'},
        {'label': 'Dynamic Products', 'url': '/dashboard/dynamic-products/'},
    ]
    for item in items:
        trail.append(item if isinstance(item, dict) else {'label': str(item)})
    return trail


@staff_member_required
def index(request):
    """List every configured block, grouped implicitly by slot ordering."""
    blocks = list(DynamicBlock.objects.prefetch_related('categories').all())
    return render(
        request,
        'dynamic_products/index.html',
        {
            'blocks': blocks,
            'breadcrumb_trail': _trail(),
            'active_section': 'settings',
        },
    )


@staff_member_required
def edit_block(request, block_id=None):
    """Create (block_id is None) or edit a DynamicBlock."""
    from plugins.installed.catalog.models import Category

    block = None if block_id is None else get_object_or_404(DynamicBlock, pk=block_id)

    if request.method == 'POST':
        block = _save_from_post(request, block)
        if block is not None:
            messages.success(request, 'Block saved.')
            return redirect('/dashboard/dynamic-products/')

    categories = list(Category.objects.order_by('name').values('pk', 'name'))
    selected_cats = (
        set(str(pk) for pk in block.categories.values_list('pk', flat=True)) if block else set()
    )
    return render(
        request,
        'dynamic_products/edit.html',
        {
            'block': block,
            'slot_choices': SLOT_CHOICES,
            'strategy_choices': STRATEGY_CHOICES,
            'categories': categories,
            'selected_cats': selected_cats,
            'tags_value': ', '.join(block.tags) if block and block.tags else '',
            'breadcrumb_trail': _trail({'label': block.name if block else 'New block'}),
            'active_section': 'settings',
        },
    )


@staff_member_required
def delete_block(request, block_id):
    block = get_object_or_404(DynamicBlock, pk=block_id)
    if request.method == 'POST':
        block.delete()
        messages.success(request, 'Block deleted.')
    return HttpResponseRedirect('/dashboard/dynamic-products/')


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _save_from_post(request, block):
    """Persist a DynamicBlock from POST data. Returns the saved instance,
    or None if validation rejected it (a message is queued)."""
    name = (request.POST.get('name') or '').strip()
    slot = (request.POST.get('slot') or '').strip()
    strategy = (request.POST.get('strategy') or '').strip()

    valid_slots = {s for s, _ in SLOT_CHOICES}
    valid_strategies = {s for s, _ in STRATEGY_CHOICES}
    if not name or slot not in valid_slots or strategy not in valid_strategies:
        messages.error(request, 'Name, a valid slot, and a valid strategy are required.')
        return None

    try:
        limit = max(1, min(int(request.POST.get('limit') or 4), 24))
    except (TypeError, ValueError):
        limit = 4
    try:
        sort_order = max(0, min(int(request.POST.get('sort_order') or 50), 999))
    except (TypeError, ValueError):
        sort_order = 50

    tags_raw = request.POST.get('tags') or ''
    tags = [t.strip() for t in tags_raw.split(',') if t.strip()]

    if block is None:
        block = DynamicBlock()
    block.name = name[:120]
    block.heading = (request.POST.get('heading') or '').strip()[:160]
    block.slot = slot
    block.strategy = strategy
    block.limit = limit
    block.sort_order = sort_order
    block.enabled = request.POST.get('enabled') in ('on', 'true', '1', 'yes')
    block.tags = tags
    block.metafield_key = (request.POST.get('metafield_key') or '').strip()[:120]
    block.metafield_value = (request.POST.get('metafield_value') or '').strip()[:255]
    block.save()

    # Category M2M.
    cat_ids = request.POST.getlist('categories')
    if cat_ids:
        from plugins.installed.catalog.models import Category

        block.categories.set(Category.objects.filter(pk__in=cat_ids))
    else:
        block.categories.clear()

    return block
