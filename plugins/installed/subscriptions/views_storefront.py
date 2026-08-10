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
    """Start a membership.

    A FREE plan activates immediately — there is nothing to charge. A PAID plan
    must not be activated here: this view had no payment leg at all, so it
    handed out memberships for nothing (the cart discount now independently
    requires evidence of payment, see membership.entitling_subscriptions). Until
    the card-collection flow lands, a paid plan is refused honestly rather than
    minting a row that says "member" and entitles nobody.
    """
    from decimal import Decimal

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

    if Decimal(str(plan.price.amount)) > 0:
        messages.error(
            request,
            f'{plan.name} is a paid plan and online sign-up is not available yet — '
            'please contact us and we will set it up for you.',
        )
        return redirect('/membership/')

    Subscription.objects.create(
        customer=request.user,
        plan=plan,
        state='trialing' if plan.trial_days else 'active',
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
