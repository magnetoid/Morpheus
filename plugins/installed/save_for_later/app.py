"""Save for later — extends the existing `wishlist` plugin.

Adds three high-yield features on top of the existing wishlist:

  1. **"Save for later" cart move** — move items out of the cart
     into a saved list without losing them when the cart expires.
  2. **Price-drop notifications** — a daily check; when any saved
     item's price drops below the snapshotted price, queue a
     notification via `notifications_center`.
  3. **Back-in-stock notifications** — same pattern: when a
     saved item that was out of stock is back, queue a
     notification.

All three ride on top of the wishlist data (we read via the hook
bus, not via direct import) and contribute to the post-purchase
notification chain (F17) for delivery.

Wishlists are shareable: a customer can publish a wishlist at
`/wishlist/<token>/` for a friend to send a gift — the gift-giving
use case that makes wishlists on-brand.
"""

from __future__ import annotations

from morpheus.app import Plugin, StorefrontBlock


class SaveForLaterPlugin(Plugin):
    name = 'save_for_later'
    label = 'Save for later'
    version = '1.0.0'
    description = (
        '"Save for later" cart move, price-drop notifications, back-in-'
        'stock notifications, and shareable wishlists (gift-giving).'
    )
    has_models = True
    requires = ['wishlist', 'notifications_center', 'consent']
    # Ships OFF until it is built: its cart button has no script or endpoint behind it.
    # A merchant can still switch it on in Dashboard → Apps.
    enabled_by_default = False

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='cart_summary_extra',
                template='save_for_later/blocks/move_buttons.html',
                priority=40,
            ),
        ]
