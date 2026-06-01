"""Marketplace's contribution to the dashboard customer-detail page.

Two pieces, both owned entirely by this plugin so disabling marketplace
removes the Vendor toggle without admin_dashboard knowing anything about
vendors:

* ``vendor_panel`` — a ``CUSTOMER_DETAIL_PANELS`` filter handler. Returns a
  panel dict (label + rendered HTML) showing the customer's vendor status
  and an on/off form. Wired in ``MarketplacePlugin.ready()``.
* ``toggle_vendor`` — a staff-gated POST endpoint that creates/activates or
  deactivates the customer's ``catalog.Vendor``. Routed in
  ``urls_dashboard.py``.

"Vendor on" = a ``catalog.Vendor`` owned by the user with ``is_active=True``.
"Vendor off" = that Vendor with ``is_active=False`` (never deleted, so the
vendor's products + order history survive a toggle).
"""

# ruff: noqa: PLC0415
# Inline imports keep this module importable before the app registry is
# ready (plugin.py imports the handler reference at ready()-time) and keep
# optional cross-plugin imports lazy.
from __future__ import annotations

import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST

logger = logging.getLogger('morpheus.marketplace')


def _owned_vendor(customer):
    """The catalog.Vendor owned by this customer, or None."""
    from plugins.installed.catalog.models import Vendor

    return Vendor.objects.filter(owner=customer).first()


def vendor_panel(value, customer=None, request=None, **kwargs):
    """CUSTOMER_DETAIL_PANELS handler — append the Vendor on/off panel.

    Filter contract: receive the running list of panel dicts, append ours,
    return the list. Fail-soft — on any error leave the list untouched so
    the customer page still renders (the hook bus also isolates us, but we
    don't want to drop the OTHER plugins' panels we were handed).
    """
    if customer is None or not isinstance(value, list):
        return value
    try:
        vendor = _owned_vendor(customer)
        html = render_to_string(
            'marketplace/customer_vendor_panel.html',
            {
                'vendor': vendor,
                'is_vendor': bool(vendor and vendor.is_active),
                'toggle_url': reverse('marketplace_dashboard:toggle_vendor', args=[customer.pk]),
            },
            request=request,
        )
        value.append({'label': 'Marketplace vendor', 'html': html, 'priority': 30})
    except Exception:  # noqa: BLE001 — never break the customer page over our panel
        logger.warning('marketplace: vendor_panel render failed', exc_info=True)
    return value


@staff_member_required
@require_POST
def toggle_vendor(request, customer_id):
    """Staff-only: turn a customer ON/OFF as a marketplace vendor.

    ``enable=1`` activates (creating the catalog.Vendor on first enable);
    ``enable=0`` deactivates. Idempotent on both sides.
    """
    from django.contrib import messages
    from django.contrib.auth import get_user_model

    from plugins.installed.catalog.models import Vendor

    customer = get_object_or_404(get_user_model(), pk=customer_id)
    enable = request.POST.get('enable') == '1'
    vendor = Vendor.objects.filter(owner=customer).first()

    if enable and vendor is None:
        base = (customer.full_name or customer.email or 'vendor').strip()
        slug = slugify(base)[:200] or f'vendor-{customer.pk}'
        # Guard the unique slug constraint without crossing into a race.
        if Vendor.objects.filter(slug=slug).exists():
            slug = f'{slug[:188]}-{str(customer.pk)[:8]}'
        Vendor.objects.create(name=base, slug=slug, owner=customer, is_active=True)
        messages.success(request, f'{base} is now a marketplace vendor.')
    elif enable and not vendor.is_active:
        vendor.is_active = True
        vendor.save(update_fields=['is_active'])
        messages.success(request, f'{vendor.name} reactivated as a vendor.')
    elif not enable and vendor is not None and vendor.is_active:
        vendor.is_active = False
        vendor.save(update_fields=['is_active'])
        messages.success(request, f'{vendor.name} is no longer an active vendor.')
    else:
        messages.info(request, 'No change — vendor already in that state.')

    return HttpResponseRedirect(reverse('admin_dashboard:customer_edit', args=[customer_id]))
