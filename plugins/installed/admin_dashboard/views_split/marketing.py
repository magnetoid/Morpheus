"""Auto-split from the legacy admin_dashboard/views.py monolith."""

from __future__ import annotations

from typing import Any

from morpheus.views import (
    HttpRequest,
    HttpResponse,
    get_object_or_404,
    messages,
    redirect,
    render,
    staff_member_required,
)
from plugins.installed.admin_dashboard.forms import (
    CouponForm,
)
from plugins.installed.admin_dashboard.views_split._shared import (
    ajax_or_redirect,
    logger,
)


@staff_member_required
def marketing_view(request: HttpRequest) -> HttpResponse:
    coupons: list[Any] = []
    try:
        from plugins.installed.marketing.models import Coupon

        coupons = list(Coupon.objects.order_by('-created_at')[:50])
    except Exception as e:  # noqa: BLE001
        logger.debug('admin_dashboard: marketing empty: %s', e)
    return render(
        request,
        'admin_dashboard/marketing.html',
        {
            'coupons': coupons,
            'active_nav': 'marketing',
        },
    )


# ── Coupons ──────────────────────────────────────────────────────────────────


@staff_member_required
def coupon_new(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = CouponForm(request.POST)
        if form.is_valid():
            coupon = form.save()
            messages.success(request, f'Coupon "{coupon.code}" created.')
            return redirect('admin_dashboard:coupon_edit', coupon_id=coupon.id)
    else:
        form = CouponForm()
    return render(
        request,
        'admin_dashboard/coupon_form.html',
        {
            'form': form,
            'coupon': None,
            'active_nav': 'marketing',
        },
    )


@staff_member_required
def coupon_edit(request: HttpRequest, coupon_id: str) -> HttpResponse:
    from plugins.installed.marketing.models import Coupon

    coupon = get_object_or_404(Coupon, pk=coupon_id)
    if request.method == 'POST':
        form = CouponForm(request.POST, instance=coupon)
        if form.is_valid():
            form.save()
            messages.success(request, 'Coupon saved.')
            return ajax_or_redirect(request, 'admin_dashboard:coupon_edit', coupon_id=coupon.id)
    else:
        form = CouponForm(instance=coupon)
    return render(
        request,
        'admin_dashboard/coupon_form.html',
        {
            'form': form,
            'coupon': coupon,
            'active_nav': 'marketing',
        },
    )


@staff_member_required
def coupon_delete(request: HttpRequest, coupon_id: str) -> HttpResponse:
    from plugins.installed.marketing.models import Coupon

    coupon = get_object_or_404(Coupon, pk=coupon_id)
    if request.method == 'POST':
        code = coupon.code
        coupon.delete()
        messages.success(request, f'Deleted coupon "{code}".')
        return redirect('admin_dashboard:marketing')
    return redirect('admin_dashboard:coupon_edit', coupon_id=coupon.id)


# ── Apps ──────────────────────────────────────────────────────────────────────
