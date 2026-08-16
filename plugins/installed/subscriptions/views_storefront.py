"""Storefront membership page — list plans, subscribe to become a member and
get the book/cart discount.

Two sign-up legs, chosen by the plan:

* **Free plan** → ``subscribe_view`` (POST) activates immediately; nothing to
  charge.
* **Paid Stripe plan** → ``subscribe_start_view`` mounts a Stripe Payment
  Element on a SetupIntent (card collected by Stripe, never seen here) →
  Stripe redirects back to ``subscribe_confirm_view`` → the SetupIntent is
  verified as *succeeded* and *this customer's*, the local subscription is
  created, and ``StripeSubscriptionAdapter.start_subscription`` charges it.
  From then on the ``invoice.paid`` / ``payment_failed`` webhooks reconcile
  state (``webhooks.py``). A paid plan on any other provider is refused
  honestly — there is no online path to pay for it.

The member discount does not trust any of this: it requires evidence the
money moved (``membership.entitling_subscriptions``), so a row created here
entitles nobody until Stripe holds the subscription.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

_MEMBERSHIP = '/membership/'


def _is_paid(plan) -> bool:
    return Decimal(str(plan.price.amount)) > 0


def _current_membership(user):
    from plugins.installed.subscriptions.models import Subscription

    if not getattr(user, 'is_authenticated', False):
        return None
    return (
        Subscription.objects.filter(customer=user, state__in=('active', 'trialing'))
        .select_related('plan')
        .first()
    )


def _stripe_signup_available() -> bool:
    """A paid plan can only be sold online when Stripe is configured on both
    ends: a secret key (payments) to mint the SetupIntent and a publishable
    key for the browser to mount the Payment Element."""
    from django.conf import settings

    from plugins.installed.subscriptions.billing.stripe_adapter import _stripe_key

    return bool(_stripe_key()) and bool(getattr(settings, 'STRIPE_PUBLIC_KEY', '') or '')


def membership_view(request):
    from plugins.installed.subscriptions.models import Plan

    plans = list(Plan.objects.filter(is_active=True).order_by('price'))
    stripe_ok = _stripe_signup_available()
    for plan in plans:
        # How the "Join" button behaves for this plan; the template stays dumb.
        plan.signup_mode = (
            'free'
            if not _is_paid(plan)
            else ('stripe' if plan.provider == 'stripe' and stripe_ok else 'unavailable')
        )
    return render(
        request,
        'subscriptions/membership.html',
        {'plans': plans, 'current': _current_membership(request.user)},
    )


@login_required
@require_http_methods(['POST'])
def subscribe_view(request):
    """Start a membership on a FREE plan.

    A paid plan is never activated here — this view has no payment leg. Before
    v0.40 it wrote ``state='active'`` for any plan and handed out memberships
    for nothing; the cart discount now independently requires evidence of
    payment (``membership.entitling_subscriptions``). A paid Stripe plan is
    routed to the card-collection flow; a paid plan on any other provider is
    refused honestly rather than minting a row that entitles nobody.
    """
    from django.utils import timezone

    from plugins.installed.subscriptions.models import Plan, Subscription

    plan = Plan.objects.filter(id=request.POST.get('plan_id'), is_active=True).first()
    if plan is None:
        messages.error(request, 'That plan is no longer available.')
        return redirect(_MEMBERSHIP)

    if _current_membership(request.user) is not None:
        messages.info(request, 'You already have an active membership.')
        return redirect(_MEMBERSHIP)

    if _is_paid(plan):
        if plan.provider == 'stripe' and _stripe_signup_available():
            return redirect(f'{_MEMBERSHIP}subscribe/{plan.id}/')
        messages.error(
            request,
            f'{plan.name} is a paid plan and online sign-up is not available yet — '
            'please contact us and we will set it up for you.',
        )
        return redirect(_MEMBERSHIP)

    Subscription.objects.create(
        customer=request.user,
        plan=plan,
        state='trialing' if plan.trial_days else 'active',
        current_period_start=timezone.now(),
    )
    messages.success(request, _welcome(plan))
    return redirect(_MEMBERSHIP)


def _welcome(plan) -> str:
    return f'Welcome aboard! You’re now a member on {plan.name}' + (
        f' — {plan.member_discount_percent}% off applies at checkout.'
        if plan.member_discount_percent
        else '.'
    )


def _paid_stripe_plan_or_redirect(request, plan_id):
    """Shared preconditions of the two card-collection views."""
    from plugins.installed.subscriptions.models import Plan

    plan = Plan.objects.filter(id=plan_id, is_active=True).first()
    if plan is None:
        messages.error(request, 'That plan is no longer available.')
        return None, redirect(_MEMBERSHIP)
    if _current_membership(request.user) is not None:
        messages.info(request, 'You already have an active membership.')
        return None, redirect(_MEMBERSHIP)
    if not _is_paid(plan) or plan.provider != 'stripe' or not _stripe_signup_available():
        messages.error(request, 'Online sign-up is not available for that plan.')
        return None, redirect(_MEMBERSHIP)
    return plan, None


@login_required
@require_http_methods(['GET'])
def subscribe_start_view(request, plan_id):
    """Card collection for a paid Stripe plan: a SetupIntent + Payment Element.

    Nothing is charged here. Stripe collects the card against the customer's
    vault (``usage='off_session'``, so the subscription can bill it later),
    then redirects the browser to ``subscribe_confirm_view``.
    """
    from django.conf import settings

    plan, resp = _paid_stripe_plan_or_redirect(request, plan_id)
    if resp is not None:
        return resp

    client_secret = ''
    try:
        from plugins.installed.payments.services import stripe as stripe_svc  # noqa: PLC0415

        client_secret = stripe_svc.create_setup_intent(request.user)
    except Exception:  # noqa: BLE001 — Stripe down: the page says so instead of 500ing
        client_secret = ''

    return render(
        request,
        'subscriptions/subscribe.html',
        {
            'plan': plan,
            'setup_client_secret': client_secret,
            'stripe_publishable_key': getattr(settings, 'STRIPE_PUBLIC_KEY', '') or '',
            'return_url': request.build_absolute_uri(f'{_MEMBERSHIP}subscribe/{plan.id}/confirm/'),
        },
    )


@login_required
@require_http_methods(['GET'])
def subscribe_confirm_view(request, plan_id):
    """Stripe's return leg: verify the SetupIntent, create + start the subscription.

    ``?setup_intent=seti_…`` is caller-supplied, so it is fetched from Stripe
    and must be *succeeded* and belong to *this* customer before its payment
    method is trusted (``payment_method_from_setup_intent``). The local row is
    created only for the duration of ``start_subscription``: if Stripe refuses,
    it is deleted again, so a failed attempt never leaves a "member" row behind
    — the membership page would otherwise greet the customer as a member of a
    plan they never paid for.
    """
    from django.utils import timezone

    from plugins.installed.subscriptions.billing.stripe_adapter import (
        StripeSubscriptionAdapter,
    )
    from plugins.installed.subscriptions.models import Subscription

    plan, resp = _paid_stripe_plan_or_redirect(request, plan_id)
    if resp is not None:
        return resp

    if (request.GET.get('redirect_status') or '') not in ('', 'succeeded'):
        messages.error(request, 'Your card was not confirmed. No membership was started.')
        return redirect(f'{_MEMBERSHIP}subscribe/{plan.id}/')

    pm_id = StripeSubscriptionAdapter.payment_method_from_setup_intent(
        request.GET.get('setup_intent') or '', request.user
    )
    if not pm_id:
        messages.error(
            request, 'We could not confirm your card. No membership was started — please try again.'
        )
        return redirect(f'{_MEMBERSHIP}subscribe/{plan.id}/')

    sub = Subscription.objects.create(
        customer=request.user,
        plan=plan,
        state='trialing' if plan.trial_days else 'active',
        current_period_start=timezone.now(),
    )
    result = StripeSubscriptionAdapter.start_subscription(sub, pm_id)
    if not result.get('success'):
        sub.delete()
        messages.error(
            request,
            'Your card was saved but the membership could not be started: '
            f'{result.get("error") or "please try again"}',
        )
        return redirect(f'{_MEMBERSHIP}subscribe/{plan.id}/')

    messages.success(request, _welcome(plan))
    return redirect(_MEMBERSHIP)
