"""Dashboard views for the promotions plugin."""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect

from core.authz import require_capability
from morpheus.app.views import render, staff_member_required


@staff_member_required
@require_capability('marketing.read')
def promotions_index(request):
    from plugins.installed.promotions.models import Promotion, PromotionApplication

    promos = Promotion.objects.all().order_by('priority')[:200]
    recent = PromotionApplication.objects.select_related('promotion').order_by('-applied_at')[:30]
    return render(
        request,
        'promotions/index.html',
        {
            'promotions': promos,
            'recent_applications': recent,
        },
    )


def _form_page(request, form, promotion):
    return render(
        request,
        'promotions/form.html',
        {
            'form': form,
            'promotion': promotion,
            'extra_rules': promotion.rules.count() - 1 if promotion is not None else 0,
        },
    )


@staff_member_required
@require_capability('marketing.write')
def promotion_new(request):
    from plugins.installed.promotions.forms import PromotionForm

    form = PromotionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        promotion = form.save()
        messages.success(request, f'Promotion "{promotion.name}" created.')
        return redirect('promotions:edit', promotion_id=promotion.pk)
    return _form_page(request, form, None)


@staff_member_required
@require_capability('marketing.write')
def promotion_edit(request, promotion_id):
    from plugins.installed.promotions.forms import PromotionForm
    from plugins.installed.promotions.models import Promotion

    promotion = get_object_or_404(Promotion, pk=promotion_id)
    form = PromotionForm(request.POST or None, instance=promotion)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Promotion saved.')
        return redirect('promotions:edit', promotion_id=promotion.pk)
    return _form_page(request, form, promotion)


@staff_member_required
@require_capability('marketing.write')
def promotion_toggle(request, promotion_id):
    """Switch a promotion on or off. A promotion that has discounted an order
    is never deleted: its applications are the audit trail."""
    from plugins.installed.promotions.models import Promotion

    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    promotion = get_object_or_404(Promotion, pk=promotion_id)
    promotion.is_active = not promotion.is_active
    promotion.save(update_fields=['is_active', 'updated_at'])
    state = 'on' if promotion.is_active else 'off'
    messages.success(request, f'"{promotion.name}" is {state}.')
    return redirect('promotions:index')
