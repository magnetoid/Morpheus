"""Read-only dashboard for the subscriptions plugin.

The full feature (rebill cron, Stripe Billing adapter, customer self-serve
plan switching) is deferred. For now the merchant can see plans + active
subscriptions through the dashboard rather than only via Django admin.
"""
from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def subscriptions_dashboard(request):
    from plugins.installed.subscriptions.models import (
        Plan, Subscription, SubscriptionInvoice,
    )
    plans = list(Plan.objects.all().order_by('-is_active', 'name'))
    subs = list(
        Subscription.objects
        .select_related('customer', 'plan')
        .order_by('-created_at')[:100]
    )
    invoices = list(
        SubscriptionInvoice.objects
        .select_related('subscription', 'subscription__customer')
        .order_by('-created_at')[:25]
    )
    return render(request, 'subscriptions/dashboard.html', {
        'plans': plans,
        'subscriptions': subs,
        'invoices': invoices,
        'active_nav': 'subscriptions',
    })
