"""Wishlist services — get-or-create per customer/session, add/remove items."""

from __future__ import annotations

import logging
import secrets

logger = logging.getLogger('morpheus.wishlist')


def get_or_create_wishlist(*, customer=None, session_key: str = '', name: str = 'My wishlist'):
    from plugins.installed.wishlist.models import Wishlist

    if customer is not None and getattr(customer, 'is_authenticated', False):
        wl, _ = Wishlist.objects.get_or_create(
            customer=customer,
            defaults={'name': name},
        )
        return wl
    if session_key:
        wl, _ = Wishlist.objects.get_or_create(
            session_key=session_key,
            customer__isnull=True,
            defaults={'name': name},
        )
        return wl
    return None


def add_item(*, wishlist, product, variant=None, note: str = '') -> WishlistItem:  # noqa: F821
    from plugins.installed.wishlist.models import WishlistItem

    item, _ = WishlistItem.objects.get_or_create(
        wishlist=wishlist,
        product=product,
        variant=variant,
        defaults={'note': note[:240]},
    )
    return item


def remove_item(*, wishlist, product, variant=None) -> int:
    from plugins.installed.wishlist.models import WishlistItem

    deleted, _ = WishlistItem.objects.filter(
        wishlist=wishlist,
        product=product,
        variant=variant,
    ).delete()
    return deleted


def make_shareable(wishlist) -> str:
    """Generate a share token + flip to public. Returns the URL token."""
    if not wishlist.share_token:
        wishlist.share_token = secrets.token_urlsafe(16)[:32]
    wishlist.is_public = True
    wishlist.save(update_fields=['share_token', 'is_public', 'updated_at'])
    return wishlist.share_token
