"""Subscriptions dashboard — view subscriptions/invoices, manage plans +
their membership discount. (Rebill cron + Stripe Billing adapter deferred.)
"""

from __future__ import annotations

import contextlib
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render
from django.utils.text import slugify


def _handle_plan_post(request) -> None:
    """Create a plan, or update its membership discount / active flag."""
    from djmoney.money import Money

    from plugins.installed.subscriptions.models import Plan

    action = request.POST.get('action')
    if action == 'create_plan':
        name = (request.POST.get('name') or '').strip()
        if not name:
            messages.error(request, 'Plan name is required.')
            return
        try:
            price = Decimal(request.POST.get('price') or '0')
        except (InvalidOperation, TypeError):
            price = Decimal('0')
        discount = 0
        with contextlib.suppress(TypeError, ValueError):
            discount = max(0, min(100, int(request.POST.get('member_discount_percent') or 0)))
        Plan.objects.create(
            name=name[:120],
            slug=slugify(name)[:140] or 'plan',
            price=Money(price, 'USD'),
            interval=(request.POST.get('interval') or 'month'),
            member_discount_percent=discount,
        )
        messages.success(request, f'Plan “{name}” created.')
    elif action == 'update_plan':
        plan = Plan.objects.filter(id=request.POST.get('plan_id')).first()
        if plan is None:
            return
        with contextlib.suppress(TypeError, ValueError):
            plan.member_discount_percent = max(
                0, min(100, int(request.POST.get('member_discount_percent') or 0))
            )
        plan.is_active = request.POST.get('is_active') == 'on'
        plan.save(update_fields=['member_discount_percent', 'is_active', 'updated_at'])
        messages.success(request, f'Plan “{plan.name}” updated.')


@staff_member_required
def subscriptions_dashboard(request):
    from plugins.installed.subscriptions.models import (
        Plan,
        Subscription,
        SubscriptionInvoice,
    )

    if request.method == 'POST':
        _handle_plan_post(request)
        return redirect('/dashboard/subscriptions/')

    plans = list(Plan.objects.all().order_by('-is_active', 'name'))
    subs = list(
        Subscription.objects.select_related('customer', 'plan').order_by('-created_at')[:100]
    )
    invoices = list(
        SubscriptionInvoice.objects.select_related(
            'subscription', 'subscription__customer'
        ).order_by('-created_at')[:25]
    )
    return render(
        request,
        'subscriptions/dashboard.html',
        {
            'plans': plans,
            'subscriptions': subs,
            'invoices': invoices,
            'active_nav': 'subscriptions',
        },
    )
