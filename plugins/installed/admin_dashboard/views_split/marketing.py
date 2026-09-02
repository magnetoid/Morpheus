"""Auto-split from the legacy admin_dashboard/views.py monolith."""

from __future__ import annotations

from typing import Any

from core.authz import require_capability
from morpheus.app.views import (
    Http404,
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
    ajax_form_errors,
    ajax_or_redirect,
    logger,
)


def _require_marketing() -> None:
    """The coupon pages are the optional marketing plugin's surface: when it
    is disabled (still importable, tables still there) they must not operate
    — 404, as if the plugin's routes were gone (ADR 0013)."""
    from plugins.registry import app_registry

    if not app_registry.is_active('marketing'):
        raise Http404('The Marketing app is disabled.')


@staff_member_required
@require_capability('marketing.read')
def marketing_view(request: HttpRequest) -> HttpResponse:
    _require_marketing()
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
@require_capability('marketing.write')
def coupon_new(request: HttpRequest) -> HttpResponse:
    _require_marketing()
    if request.method == 'POST':
        form = CouponForm(request.POST)
        if form.is_valid():
            coupon = form.save()
            messages.success(request, f'Coupon "{coupon.code}" created.')
            return ajax_or_redirect(
                request, 'admin_dashboard:coupon_edit', coupon_id=coupon.id, follow=True
            )
        if (error_response := ajax_form_errors(request, form)) is not None:
            return error_response
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
@require_capability('marketing.write')
def coupon_edit(request: HttpRequest, coupon_id: str) -> HttpResponse:
    _require_marketing()
    from plugins.installed.marketing.models import Coupon

    coupon = get_object_or_404(Coupon, pk=coupon_id)
    if request.method == 'POST':
        form = CouponForm(request.POST, instance=coupon)
        if form.is_valid():
            form.save()
            messages.success(request, 'Coupon saved.')
            return ajax_or_redirect(request, 'admin_dashboard:coupon_edit', coupon_id=coupon.id)
        if (error_response := ajax_form_errors(request, form)) is not None:
            return error_response
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
@require_capability('marketing.write')
def coupon_delete(request: HttpRequest, coupon_id: str) -> HttpResponse:
    _require_marketing()
    from plugins.installed.marketing.models import Coupon

    coupon = get_object_or_404(Coupon, pk=coupon_id)
    if request.method == 'POST':
        code = coupon.code
        coupon.delete()
        messages.success(request, f'Deleted coupon "{code}".')
        return redirect('admin_dashboard:marketing')
    return redirect('admin_dashboard:coupon_edit', coupon_id=coupon.id)


# ── Apps ──────────────────────────────────────────────────────────────────────
