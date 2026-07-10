"""orders' slice of the GDPR export/erasure hooks (CUSTOMER_DATA_EXPORT /
CUSTOMER_ANONYMISE). Owned here so customers never imports orders models."""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.orders.gdpr')


def on_customer_export(value, customer=None, **kwargs):
    """orders.json — Orders + items snapshot."""
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
    value['orders.json'] = orders
    return value


def on_customer_anonymise(customer=None, sentinel_email='', **kwargs):
    """Keep order rows for accounting; scrub every identifying field."""
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
