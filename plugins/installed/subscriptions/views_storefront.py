"""Storefront membership page — list plans, subscribe to become a member and
get the book/cart discount."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods


def membership_view(request):
    from plugins.installed.subscriptions.models import Plan, Subscription

    plans = Plan.objects.filter(is_active=True).order_by('price')
    current = None
    if getattr(request.user, 'is_authenticated', False):
        current = (
            Subscription.objects.filter(customer=request.user, state__in=('active', 'trialing'))
            .select_related('plan')
            .first()
        )
    return render(
        request,
        'subscriptions/membership.html',
        {'plans': plans, 'current': current},
    )


@login_required
@require_http_methods(['POST'])
def subscribe_view(request):
    """Subscribe the logged-in customer to a plan (manual provider → active)."""
    from django.utils import timezone

    from plugins.installed.subscriptions.models import Plan, Subscription

    plan = Plan.objects.filter(id=request.POST.get('plan_id'), is_active=True).first()
    if plan is None:
        messages.error(request, 'That plan is no longer available.')
        return redirect('/membership/')

    existing = Subscription.objects.filter(
        customer=request.user, state__in=('active', 'trialing')
    ).first()
    if existing is not None:
        messages.info(request, 'You already have an active membership.')
        return redirect('/membership/')

    state = 'trialing' if plan.trial_days else 'active'
    Subscription.objects.create(
        customer=request.user,
        plan=plan,
        state=state,
        current_period_start=timezone.now(),
    )
    messages.success(
        request,
        f'Welcome aboard! You’re now a member on {plan.name}'
        + (
            f' — {plan.member_discount_percent}% off applies at checkout.'
            if plan.member_discount_percent
            else '.'
        ),
    )
    return redirect('/membership/')
