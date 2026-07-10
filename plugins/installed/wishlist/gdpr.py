"""wishlist's slice of the GDPR export/erasure hooks."""

from __future__ import annotations


def on_customer_export(value, customer=None, **kwargs):
    from plugins.installed.wishlist.models import WishlistItem  # noqa: PLC0415

    value['wishlist.json'] = [
        {
            'wishlist': w.wishlist.name,
            'product': getattr(w.product, 'name', ''),
            'note': w.note,
            'added_at': w.added_at,
        }
        for w in WishlistItem.objects.filter(wishlist__customer=customer).select_related(
            'product', 'wishlist'
        )
    ]
    return value


def on_customer_anonymise(customer=None, **kwargs):
    """No fiscal hold on wishlists — delete outright."""
    from plugins.installed.wishlist.models import Wishlist  # noqa: PLC0415

    Wishlist.objects.filter(customer=customer).delete()
