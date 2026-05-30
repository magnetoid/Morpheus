"""Customer-side business logic.

`update_cdp_metrics` is the canonical writer for Customer.lifetime_value /
.purchase_count / .last_order_at — kept in one place so the dashboard,
ORDER_PAID hook, and any backfill script all agree on what "LTV" means.

`gather_customer_data` / `anonymise_customer` implement the GDPR Art. 15
(right to access) + Art. 17 (right to be forgotten) workflows used by the
storefront /account/data-export/ and /account/delete/ endpoints. They
import optional plugin models lazily inside try/except so disabling a
plugin doesn't break the export or the delete.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger('morpheus.customers.cdp')


def update_cdp_metrics(order) -> None:
    """Bump the contact's CDP rollups for a freshly-paid order.

    Uses ``F()`` increments so concurrent ORDER_PAID hooks for the same
    customer don't trample each other. Idempotency is the caller's job —
    we expect ORDER_PAID to fire once per state transition.
    """
    customer = getattr(order, 'customer', None)
    if customer is None or not customer.pk:
        return
    total_amount = getattr(order, 'total', None)
    if hasattr(total_amount, 'amount'):
        total_amount = total_amount.amount
    if total_amount is None:
        return
    try:
        total_amount = Decimal(str(total_amount))
    except Exception:  # noqa: BLE001
        logger.debug('customers.cdp: non-decimal total on order %s', getattr(order, 'pk', '?'))
        return

    # Order has `placed_at` (set on order create); `created_at` was a typo
    # that silently fell through to `now()` and clobbered the real placement
    # time on every paid-order hook fire.
    placed_at = (
        getattr(order, 'placed_at', None) or getattr(order, 'created_at', None) or timezone.now()
    )
    Customer = customer.__class__
    with transaction.atomic():
        (
            Customer.objects.filter(pk=customer.pk).update(
                lifetime_value=F('lifetime_value') + total_amount,
                purchase_count=F('purchase_count') + 1,
                last_order_at=placed_at,
            )
        )


# ── GDPR Art. 15 / Art. 17 ─────────────────────────────────────────────


def gather_customer_data(customer) -> dict:
    """Return a dict of {filename: data} covering every category we hold
    about this customer. Used by the data-export endpoint to build a ZIP.

    Optional plugins (consent / wishlist / loyalty_points / affiliates)
    are imported lazily — if the plugin is disabled, that file is
    omitted from the export.
    """
    out: dict = {}

    # account.json — identity + profile + CDP rollups
    out['account.json'] = {
        'id': str(customer.pk),
        'email': customer.email,
        'first_name': customer.first_name,
        'last_name': customer.last_name,
        'phone': getattr(customer, 'phone', ''),
        'company': getattr(customer, 'company', ''),
        'date_of_birth': getattr(customer, 'date_of_birth', None),
        'accepts_marketing': getattr(customer, 'accepts_marketing', False),
        'source': getattr(customer, 'source', ''),
        'is_verified': getattr(customer, 'is_verified', False),
        'lifetime_value': getattr(customer, 'lifetime_value', None),
        'purchase_count': getattr(customer, 'purchase_count', None),
        'last_order_at': getattr(customer, 'last_order_at', None),
        'created_at': getattr(customer, 'date_joined', None),
        'metadata': getattr(customer, 'metadata', {}) or {},
    }

    # addresses.json — saved Addresses
    try:
        addresses = []
        for a in customer.addresses.all():
            addresses.append(
                {
                    'id': str(a.id),
                    'address_type': a.address_type,
                    'first_name': a.first_name,
                    'last_name': a.last_name,
                    'company': a.company,
                    'address_line1': a.address_line1,
                    'address_line2': a.address_line2,
                    'city': a.city,
                    'state': a.state,
                    'postal_code': a.postal_code,
                    'country': a.country,
                    'phone': a.phone,
                    'is_default': a.is_default,
                    'created_at': a.created_at,
                }
            )
        out['addresses.json'] = addresses
    except Exception:  # noqa: BLE001
        logger.debug('gdpr export: addresses unavailable', exc_info=True)

    # orders.json — Orders + items snapshot
    try:
        from plugins.installed.orders.models import Order  # noqa: PLC0415

        orders = []
        qs = Order.objects.filter(customer=customer).prefetch_related('items')
        for o in qs:
            orders.append(
                {
                    'order_number': o.order_number,
                    'status': o.status,
                    'payment_status': o.payment_status,
                    'email': o.email,
                    'subtotal': str(o.subtotal),
                    'shipping_total': str(o.shipping_total),
                    'tax_total': str(o.tax_total),
                    'discount_total': str(o.discount_total),
                    'total': str(o.total),
                    'shipping_address': o.shipping_address,
                    'billing_address': o.billing_address,
                    'coupon_code': o.coupon_code,
                    'shipping_method': o.shipping_method,
                    'tracking_number': o.tracking_number,
                    'customer_notes': o.customer_notes,
                    'placed_at': o.placed_at,
                    'updated_at': o.updated_at,
                    'items': [
                        {
                            'product_name': it.product_name,
                            'variant_name': it.variant_name,
                            'sku': it.sku,
                            'quantity': it.quantity,
                            'unit_price': str(it.unit_price),
                            'total_price': str(it.total_price),
                        }
                        for it in o.items.all()
                    ],
                }
            )
        out['orders.json'] = orders
    except Exception:  # noqa: BLE001
        logger.debug('gdpr export: orders unavailable', exc_info=True)

    # reviews.json — catalog.Review rows the customer wrote
    try:
        from plugins.installed.catalog.models import Review  # noqa: PLC0415

        reviews = []
        for r in Review.objects.filter(customer=customer).select_related('product'):
            reviews.append(
                {
                    'product': getattr(r.product, 'name', ''),
                    'rating': r.rating,
                    'title': r.title,
                    'body': r.body,
                    'is_approved': r.is_approved,
                    'is_verified_purchase': r.is_verified_purchase,
                    'created_at': r.created_at,
                }
            )
        out['reviews.json'] = reviews
    except Exception:  # noqa: BLE001
        logger.debug('gdpr export: reviews unavailable', exc_info=True)

    # consent.json — ConsentLog audit trail
    try:
        from plugins.installed.consent.models import ConsentLog  # noqa: PLC0415

        out['consent.json'] = [
            {
                'necessary': c.necessary,
                'analytics': c.analytics,
                'marketing': c.marketing,
                'functional': c.functional,
                'user_agent': c.user_agent,
                'created_at': c.created_at,
            }
            for c in ConsentLog.objects.filter(customer=customer)
        ]
    except Exception:  # noqa: BLE001
        logger.debug('gdpr export: consent unavailable', exc_info=True)

    # wishlist.json — saved products
    try:
        from plugins.installed.wishlist.models import WishlistItem  # noqa: PLC0415

        items = []
        for w in WishlistItem.objects.filter(wishlist__customer=customer).select_related(
            'product', 'wishlist'
        ):
            items.append(
                {
                    'wishlist': w.wishlist.name,
                    'product': getattr(w.product, 'name', ''),
                    'note': w.note,
                    'added_at': w.added_at,
                }
            )
        out['wishlist.json'] = items
    except Exception:  # noqa: BLE001
        logger.debug('gdpr export: wishlist unavailable', exc_info=True)

    # loyalty.json — points balance + ledger
    try:
        from plugins.installed.loyalty_points.models import PointsTransaction  # noqa: PLC0415
        from plugins.installed.loyalty_points.services import get_balance  # noqa: PLC0415

        out['loyalty.json'] = {
            'balance': get_balance(customer),
            'transactions': [
                {
                    'points': t.points,
                    'reason': t.reason,
                    'order_number': t.order_number,
                    'note': t.note,
                    'created_at': t.created_at,
                }
                for t in PointsTransaction.objects.filter(customer=customer)
            ],
        }
    except Exception:  # noqa: BLE001
        logger.debug('gdpr export: loyalty unavailable', exc_info=True)

    # affiliate.json — Affiliate row + commissions
    try:
        from plugins.installed.affiliates.models import (  # noqa: PLC0415
            Affiliate,
            AffiliateConversion,
        )

        affiliates = []
        for aff in Affiliate.objects.filter(user=customer):
            conversions = [
                {
                    'order': c.order.order_number if c.order_id else '',
                    'commission': str(c.commission),
                    'status': c.status,
                    'created_at': c.created_at,
                }
                for c in AffiliateConversion.objects.filter(affiliate=aff).select_related('order')
            ]
            affiliates.append(
                {
                    'handle': aff.handle,
                    'status': aff.status,
                    'display_name': aff.display_name,
                    'company': aff.company,
                    'payout_email': aff.payout_email,
                    'accrued_balance': str(aff.accrued_balance),
                    'lifetime_paid': str(aff.lifetime_paid),
                    'created_at': aff.created_at,
                    'approved_at': aff.approved_at,
                    'conversions': conversions,
                }
            )
        out['affiliate.json'] = affiliates
    except Exception:  # noqa: BLE001
        logger.debug('gdpr export: affiliate unavailable', exc_info=True)

    return out


def anonymise_customer(customer) -> None:
    """Anonymise the customer in-place: preserves order history for
    fiscal / legal hold, but strips all PII from the record itself and
    from any other table that joins on the customer FK.

    - Customer: email/name/phone replaced with sentinel values,
      ``is_active=False`` so login is blocked.
    - Orders: customer_notes wiped, ip/user_agent cleared, address
      JSON blobs redacted; order_number + totals kept for accounting.
    - Reviews: body kept (the review remains useful to other readers),
      but title is wiped to "Deleted user" so any name in the title
      doesn't leak.
    - Wishlist: deleted (no fiscal hold).
    - Addresses: deleted.
    - PaymentMethod metadata: deleted (Stripe holds the actual card).

    Wrap the caller in ``transaction.atomic()``.
    """
    if customer is None or not customer.pk:
        return

    sentinel_email = f'deleted-{uuid.uuid4().hex}@dotbooks.invalid'

    # Orders: keep the row for accounting; scrub identifying fields.
    try:
        from plugins.installed.orders.models import Order  # noqa: PLC0415

        for o in Order.objects.filter(customer=customer):
            o.email = sentinel_email
            o.customer_notes = '[redacted]'
            o.ip_address = None
            o.user_agent = ''
            o.shipping_address = {'redacted': True}
            o.billing_address = {'redacted': True}
            o.save(
                update_fields=[
                    'email',
                    'customer_notes',
                    'ip_address',
                    'user_agent',
                    'shipping_address',
                    'billing_address',
                ]
            )
    except Exception:  # noqa: BLE001
        logger.exception('gdpr: scrubbing Orders failed for customer %s', customer.pk)

    # Reviews: anonymise the title (no separate author_name field —
    # author identity comes from the FK, which we re-point to the
    # anonymised user record).
    try:
        from plugins.installed.catalog.models import Review  # noqa: PLC0415

        Review.objects.filter(customer=customer).update(title='Deleted user')
    except Exception:  # noqa: BLE001
        logger.exception('gdpr: anonymising Reviews failed for customer %s', customer.pk)

    # Wishlist + items
    try:
        from plugins.installed.wishlist.models import Wishlist  # noqa: PLC0415

        Wishlist.objects.filter(customer=customer).delete()
    except Exception:  # noqa: BLE001
        logger.exception('gdpr: deleting Wishlist failed for customer %s', customer.pk)

    # Saved addresses
    try:
        customer.addresses.all().delete()
    except Exception:  # noqa: BLE001
        logger.exception('gdpr: deleting Addresses failed for customer %s', customer.pk)

    # Payment-method metadata (Stripe holds the card)
    try:
        from plugins.installed.payments.models import PaymentMethod  # noqa: PLC0415

        PaymentMethod.objects.filter(customer=customer).delete()
    except Exception:  # noqa: BLE001
        logger.exception('gdpr: deleting PaymentMethods failed for customer %s', customer.pk)

    # Finally, anonymise the Customer row itself.
    customer.email = sentinel_email
    customer.username = sentinel_email
    customer.first_name = 'Deleted'
    customer.last_name = 'user'
    customer.phone = ''
    customer.company = ''
    customer.notes = ''
    customer.metadata = {}
    customer.accepts_marketing = False
    customer.date_of_birth = None
    customer.is_active = False
    customer.save(
        update_fields=[
            'email',
            'username',
            'first_name',
            'last_name',
            'phone',
            'company',
            'notes',
            'metadata',
            'accepts_marketing',
            'date_of_birth',
            'is_active',
        ]
    )
