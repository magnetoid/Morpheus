"""Dashboard views for the promotions plugin."""

from __future__ import annotations

from morpheus.app.views import render, staff_member_required


@staff_member_required
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
