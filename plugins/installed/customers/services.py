"""Customer-side business logic.

`set_cdp_metrics` is the one writer for Customer.lifetime_value /
.purchase_count / .last_order_at; the orders app calls it with its sales rule
(``orders.customer_totals``), so the Contacts list, RFM and Linda read the same
figure as every sales report.

`gather_customer_data` / `anonymise_customer` implement the GDPR Art. 15
(right to access) + Art. 17 (right to be forgotten) workflows used by the
storefront /account/data-export/ and /account/delete/ endpoints. Each
plugin contributes its own slice through the CUSTOMER_DATA_EXPORT filter /
CUSTOMER_ANONYMISE event, so a disabled plugin's data simply drops out.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal

logger = logging.getLogger('morpheus.customers.cdp')


def set_cdp_metrics(customer_pk, *, purchase_count: int, lifetime_value, last_order_at) -> None:
    """Write a contact's rollups: what the orders app counts as their sales
    (``orders.customer_totals``), never a running sum. Each paid order used to
    add its whole total, so a refund or a cancellation never came off."""
    from plugins.installed.customers.models import Customer  # noqa: PLC0415

    Customer.objects.filter(pk=customer_pk).update(
        purchase_count=int(purchase_count or 0),
        lifetime_value=Decimal(str(lifetime_value or 0)),
        last_order_at=last_order_at,
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

    # Every other category is contributed by its owning plugin through the
    # CUSTOMER_DATA_EXPORT filter (orders.json, reviews.json, consent.json,
    # wishlist.json, loyalty.json, affiliate.json, …). A disabled plugin's
    # file simply never appears — the bus gates on active state.
    from morpheus.core import MorpheusEvents, hook_registry  # noqa: PLC0415

    out = hook_registry.filter(MorpheusEvents.CUSTOMER_DATA_EXPORT, out, customer=customer)

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

    # RFC-2606 reserved .invalid TLD, brand-neutral (this is the generic
    # customers plugin — not the dot_books store).
    sentinel_email = f'deleted-{uuid.uuid4().hex}@deleted.invalid'

    # Each owning plugin scrubs/deletes its own rows (orders keep totals for
    # fiscal hold but lose PII; wishlist and stored payment methods delete;
    # review titles anonymise) via the CUSTOMER_ANONYMISE event. The bus
    # isolates a broken handler and skips disabled owners.
    from morpheus.core import MorpheusEvents, hook_registry  # noqa: PLC0415

    hook_registry.fire(
        MorpheusEvents.CUSTOMER_ANONYMISE, customer=customer, sentinel_email=sentinel_email
    )

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
