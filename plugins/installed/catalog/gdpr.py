"""catalog's slice of the GDPR export/erasure hooks — the customer's reviews."""

from __future__ import annotations


def on_customer_export(value, customer=None, **kwargs):
    """reviews.json — catalog.Review rows the customer wrote."""
    from plugins.installed.catalog.models import Review  # noqa: PLC0415

    value['reviews.json'] = [
        {
            'product': getattr(r.product, 'name', ''),
            'rating': r.rating,
            'title': r.title,
            'body': r.body,
            'is_approved': r.is_approved,
            'is_verified_purchase': r.is_verified_purchase,
            'created_at': r.created_at,
        }
        for r in Review.objects.filter(customer=customer).select_related('product')
    ]
    return value


def on_customer_anonymise(customer=None, **kwargs):
    """Body stays useful to other readers; the title could carry a name."""
    from plugins.installed.catalog.models import Review  # noqa: PLC0415

    Review.objects.filter(customer=customer).update(title='Deleted user')
