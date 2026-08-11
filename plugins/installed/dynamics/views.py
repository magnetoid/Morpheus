"""dynamics — dashboard config views (staff-only).

A small CRUD over :class:`DynamicBlock`: list, create/edit, delete. All
templates live under this plugin's own ``templates/dynamics/``;
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

from morpheus.app import dashboard_trail

from .models import (
    SLOT_CHOICES,
    STRATEGY_CHOICES,
    SURFACE_CHOICES,
    DynamicBlock,
)

# Sensible default sizes when a merchant takes control of a surface.
_SURFACE_LIMITS = {'home_hero': 4, 'home_featured': 8, 'home_staff_picks': 8}


def _trail(*items):
    return dashboard_trail('Dynamics', '/dashboard/dynamics/', *items)


@staff_member_required
def index(request):
    """Merchandising console: surfaces takeover table + carousel blocks."""
    blocks = list(DynamicBlock.objects.prefetch_related('categories').all())
    by_surface: dict = {}
    for b in blocks:
        if b.surface and b.enabled and b.surface not in by_surface:
            by_surface[b.surface] = b
    surfaces = [
        {'key': key, 'label': label, 'block': by_surface.get(key)} for key, label in SURFACE_CHOICES
    ]
    slot_blocks = [b for b in blocks if b.slot]
    return render(
        request,
        'dynamics/index.html',
        {
            'surfaces': surfaces,
            'blocks': slot_blocks,
            'breadcrumb_trail': _trail(),
            'active_section': 'settings',
        },
    )


@staff_member_required
def take_control(request, surface):
    """One click: bind a smart-strategy block to a theme surface."""
    valid = dict(SURFACE_CHOICES)
    if request.method != 'POST' or surface not in valid:
        return HttpResponseRedirect('/dashboard/dynamics/')
    existing = (
        DynamicBlock.objects.filter(surface=surface, enabled=True).order_by('sort_order').first()
    )
    if existing is not None:
        return redirect(f'/dashboard/dynamics/{existing.pk}/')
    block = DynamicBlock.objects.create(
        name=valid[surface],
        surface=surface,
        strategy='smart',
        limit=_SURFACE_LIMITS.get(surface, 12),
        enabled=True,
    )
    messages.success(
        request,
        f'Dynamics now controls “{valid[surface]}” with the Smart strategy — tune it below.',
    )
    return redirect(f'/dashboard/dynamics/{block.pk}/')


@staff_member_required
def preview_block(request, block_id):
    """Live preview: the block's picks with per-product score explanations.

    ``?segment=`` previews an autopilot block as a specific visitor segment
    (smart is segment-independent; the selector notes that).
    """
    from .segments import SEGMENT_CHOICES
    from .services import explain_block

    block = get_object_or_404(DynamicBlock, pk=block_id)
    segment = (request.GET.get('segment') or '').strip()
    if segment:
        block.segment_override = segment  # in-memory only — preview, not saved
    rows = explain_block(block, request=request)
    # Template-friendly component bars: ordered [{label, value, pct}].
    for r in rows:
        r['bars'] = [
            {'label': key, 'value': val, 'pct': int(round(val * 100))}
            for key, val in (r['components'] or {}).items()
        ]
    return render(
        request,
        'dynamics/preview.html',
        {
            # 'blk', not 'block' — see edit_block.
            'blk': block,
            'rows': rows,
            'segment': segment,
            'segment_choices': SEGMENT_CHOICES,
            'breadcrumb_trail': _trail(
                {'label': block.name, 'url': f'/dashboard/dynamics/{block.pk}/'},
                'Preview',
            ),
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
            return redirect('/dashboard/dynamics/')

    categories = list(Category.objects.order_by('name').values('pk', 'name'))
    selected_cats = (
        set(str(pk) for pk in block.categories.values_list('pk', flat=True)) if block else set()
    )
    return render(
        request,
        'dynamics/edit.html',
        {
            # 'blk', not 'block' — inside {% block %} tags Django shadows the
            # context var 'block' with the template BlockNode.
            'blk': block,
            'slot_choices': SLOT_CHOICES,
            'surface_choices': SURFACE_CHOICES,
            'strategy_choices': STRATEGY_CHOICES,
            'categories': categories,
            'selected_cats': selected_cats,
            'tags_value': ', '.join(block.tags) if block and block.tags else '',
            'pinned_value': ', '.join(str(x) for x in block.pinned_product_ids)
            if block and block.pinned_product_ids
            else '',
            'excluded_value': ', '.join(str(x) for x in block.excluded_product_ids)
            if block and block.excluded_product_ids
            else '',
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
    return HttpResponseRedirect('/dashboard/dynamics/')


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _save_from_post(request, block):
    """Persist a DynamicBlock from POST data. Returns the saved instance,
    or None if validation rejected it (a message is queued)."""
    name = (request.POST.get('name') or '').strip()
    slot = (request.POST.get('slot') or '').strip()
    surface = (request.POST.get('surface') or '').strip()
    strategy = (request.POST.get('strategy') or '').strip()

    valid_slots = {s for s, _ in SLOT_CHOICES}
    valid_surfaces = {s for s, _ in SURFACE_CHOICES}
    slot_ok = slot in valid_slots or (not slot and surface)
    surface_ok = not surface or surface in valid_surfaces
    strategy_ok = strategy in {s for s, _ in STRATEGY_CHOICES}
    if not name or not slot_ok or not surface_ok or not strategy_ok:
        messages.error(request, 'Name, a valid strategy, and a slot or a surface are required.')
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
    block.surface = surface
    block.strategy = strategy
    block.limit = limit
    block.sort_order = sort_order
    block.enabled = request.POST.get('enabled') in ('on', 'true', '1', 'yes')
    block.tags = tags
    block.metafield_key = (request.POST.get('metafield_key') or '').strip()[:120]
    block.metafield_value = (request.POST.get('metafield_value') or '').strip()[:255]
    _apply_option_fields(block, request)
    block.save()

    # Category M2M.
    cat_ids = request.POST.getlist('categories')
    if cat_ids:
        from plugins.installed.catalog.models import Category

        block.categories.set(Category.objects.filter(pk__in=cat_ids))
    else:
        block.categories.clear()

    return block


def _checked(request, key) -> bool:
    return request.POST.get(key) in ('on', 'true', '1', 'yes')


def _apply_option_fields(block, request) -> None:
    """Parse the B2/B3/B4 option fields off POST onto `block` (before save)."""
    from decimal import Decimal, InvalidOperation

    def _dec(key):
        raw = (request.POST.get(key) or '').strip()
        if not raw:
            return None
        try:
            return Decimal(raw)
        except InvalidOperation:
            return None

    def _int(key, lo, hi, default):
        raw = (request.POST.get(key) or '').strip()
        if not raw:
            return default
        try:
            return max(lo, min(int(raw), hi))
        except (TypeError, ValueError):
            return default

    def _ids(key):
        return [t.strip() for t in (request.POST.get(key) or '').split(',') if t.strip()]

    # B2 — filters
    block.exclude_out_of_stock = _checked(request, 'exclude_out_of_stock')
    block.exclude_purchased = _checked(request, 'exclude_purchased')
    block.price_min = _dec('price_min')
    block.price_max = _dec('price_max')
    block.pinned_product_ids = _ids('pinned_product_ids')
    block.excluded_product_ids = _ids('excluded_product_ids')
    # B3 — display
    block.layout = 'grid' if request.POST.get('layout') == 'grid' else 'carousel'
    block.columns = _int('columns', 2, 6, 4)
    block.show_price = _checked(request, 'show_price')
    block.show_title = _checked(request, 'show_title')
    block.show_reason = _checked(request, 'show_reason')
    # B4 — autopilot overrides (blank → default)
    rate = _dec('exploration_rate')
    block.exploration_rate = (
        float(max(Decimal('0'), min(rate, Decimal('1')))) if rate is not None else None
    )
    block.diversity_cap = _int('diversity_cap', 1, 12, None)
    block.segment_override = (request.POST.get('segment_override') or '').strip()[:64]


# ---------------------------------------------------------------------------
# Autopilot merchandiser — review queue
# ---------------------------------------------------------------------------


@staff_member_required
def proposals(request):
    """Human-checkpoint review queue for the nightly merchandiser autopilot."""
    from .models import MerchandisingProposal

    return render(
        request,
        'dynamics/proposals.html',
        {
            'open_proposals': list(MerchandisingProposal.objects.filter(status='proposed')),
            'recent_proposals': list(
                MerchandisingProposal.objects.exclude(status='proposed').order_by('-reviewed_at')[
                    :10
                ]
            ),
            'breadcrumb_trail': _trail({'label': 'Autopilot proposals'}),
            'active_section': 'settings',
        },
    )


@staff_member_required
def proposal_action(request, proposal_id):
    """Approve (apply the low-risk config action) or dismiss one proposal."""
    from . import autopilot
    from .models import MerchandisingProposal

    proposal = get_object_or_404(MerchandisingProposal, pk=proposal_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            applied = autopilot.apply_proposal(proposal, actor=request.user)
            messages.success(request, 'Applied.' if applied else 'Acknowledged.')
        elif action == 'dismiss':
            autopilot.dismiss_proposal(proposal, actor=request.user)
            messages.info(request, 'Dismissed.')
    return HttpResponseRedirect('/dashboard/dynamics/proposals/')
