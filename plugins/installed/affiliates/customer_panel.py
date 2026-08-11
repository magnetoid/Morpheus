"""Affiliates' contribution to the dashboard customer-detail page.

Two pieces, both owned entirely by this plugin so disabling affiliates
removes the Affiliate toggle without admin_dashboard knowing anything about
affiliates:

* ``affiliate_panel`` — a ``CUSTOMER_DETAIL_PANELS`` filter handler. Returns
  a panel dict (label + rendered HTML) showing the customer's affiliate
  status and an on/off form. Wired in ``AffiliatesPlugin.ready()``.
* ``toggle_affiliate`` — a staff-gated POST endpoint that approves or
  suspends the customer's ``affiliates.Affiliate``. Routed in
  ``urls_dashboard.py``.

"Affiliate on" = an ``Affiliate`` for the user with ``status='approved'``.
"Affiliate off" = that Affiliate with ``status='suspended'`` (never deleted,
so conversion + payout history survive a toggle). First enable enrolls the
user into the oldest active ``AffiliateProgram``.
"""

# ruff: noqa: PLC0415
# Inline imports keep this module importable before the app registry is
# ready (app.py imports the handler reference at ready()-time) and keep
# optional cross-plugin imports lazy.
from __future__ import annotations

import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

logger = logging.getLogger('morpheus.affiliates')


def _affiliate_for(customer):
    """The Affiliate row for this customer, or None."""
    from plugins.installed.affiliates.models import Affiliate

    return Affiliate.objects.select_related('program').filter(user=customer).first()


def _default_program():
    """Oldest active AffiliateProgram a new enrollee joins, or None."""
    from plugins.installed.affiliates.models import AffiliateProgram

    return AffiliateProgram.objects.filter(is_active=True).order_by('created_at').first()


def affiliate_panel(value, customer=None, request=None, **kwargs):
    """CUSTOMER_DETAIL_PANELS handler — append the Affiliate on/off panel.

    Filter contract: receive the running list of panel dicts, append ours,
    return the list. Fail-soft — on any error leave the list untouched so
    the customer page still renders (and the OTHER plugins' panels we were
    handed survive).
    """
    if customer is None or not isinstance(value, list):
        return value
    try:
        affiliate = _affiliate_for(customer)
        html = render_to_string(
            'affiliates/customer_affiliate_panel.html',
            {
                'affiliate': affiliate,
                'is_affiliate': bool(affiliate and affiliate.status == 'approved'),
                'no_program': _default_program() is None,
                'toggle_url': reverse('affiliates_dashboard:toggle_affiliate', args=[customer.pk]),
            },
            request=request,
        )
        value.append({'label': 'Affiliate', 'html': html, 'priority': 40})
    except Exception:  # noqa: BLE001 — never break the customer page over our panel
        logger.warning('affiliates: affiliate_panel render failed', exc_info=True)
    return value


@staff_member_required
@require_POST
def toggle_affiliate(request, customer_id):
    """Staff-only: approve or suspend a customer as an affiliate.

    ``enable=1`` approves (enrolling into the default program + minting a
    handle on first enable); ``enable=0`` suspends. Idempotent on both sides.
    """
    from django.contrib import messages
    from django.contrib.auth import get_user_model

    from plugins.installed.affiliates.models import Affiliate
    from plugins.installed.affiliates.services import (
        HandleUnavailable,
        generate_unique_handle,
    )

    customer = get_object_or_404(get_user_model(), pk=customer_id)
    enable = request.POST.get('enable') == '1'
    affiliate = _affiliate_for(customer)
    redirect_to = HttpResponseRedirect(reverse('admin_dashboard:customer_edit', args=[customer_id]))

    if enable and affiliate is None:
        program = _default_program()
        if program is None:
            messages.error(
                request, 'No active affiliate program — create one before enrolling users.'
            )
            return redirect_to
        try:
            handle = generate_unique_handle(customer)
        except HandleUnavailable:
            messages.error(request, "Couldn't mint a unique affiliate handle for this user.")
            return redirect_to
        Affiliate.objects.create(
            program=program,
            user=customer,
            handle=handle,
            status='approved',
            display_name=(customer.full_name or '')[:200],
            payout_email=(customer.email or '')[:254],
            approved_at=timezone.now(),
        )
        messages.success(request, f'{customer.email} is now an approved affiliate.')
    elif enable and affiliate.status != 'approved':
        affiliate.status = 'approved'
        affiliate.approved_at = timezone.now()
        affiliate.save(update_fields=['status', 'approved_at'])
        messages.success(request, f'Affiliate {affiliate.handle} approved.')
    elif not enable and affiliate is not None and affiliate.status == 'approved':
        affiliate.status = 'suspended'
        affiliate.save(update_fields=['status'])
        messages.success(request, f'Affiliate {affiliate.handle} suspended.')
    else:
        messages.info(request, 'No change — affiliate already in that state.')

    return redirect_to
