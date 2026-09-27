"""Tell back-in-stock subscribers when their product can be bought again.

Every theme's product page posts "email me when it's back" to
`views.back_in_stock_subscribe`, which stores a `BackInStockSubscription` and
promises an email. The email task (`tasks.notify_back_in_stock`) existed, but
nothing ever enqueued it — so no subscriber was ever told, however much stock
came back in.
"""

from __future__ import annotations

import logging

from django.db import transaction

logger = logging.getLogger('morpheus.inventory')


def on_stock_level_saved(sender, instance, **kwargs) -> None:
    """post_save(StockLevel): the level has sellable units → queue the waiting.

    `notify_back_in_stock` stamps `notified_at` on every subscription it
    mails, so once it has run this finds nobody waiting. The enqueue waits for
    the stock write to commit, so a rolled-back restock never emails anyone.
    """
    if instance.is_out_of_stock:
        return
    # A raw post_save connection is not gated by the hook bus's active-owner
    # check, so a runtime-disabled inventory app must opt itself out.
    from plugins.registry import app_registry  # noqa: PLC0415

    if not app_registry.is_active('inventory'):
        return
    from plugins.installed.inventory.models import BackInStockSubscription  # noqa: PLC0415

    product_id = (
        BackInStockSubscription.objects.filter(
            product__variants__id=instance.variant_id, notified_at__isnull=True
        )
        .values_list('product_id', flat=True)
        .first()
    )
    if product_id is None:
        return

    def _enqueue():
        from plugins.installed.inventory.tasks import notify_back_in_stock  # noqa: PLC0415

        try:
            notify_back_in_stock.delay(str(product_id))
        except Exception as e:  # noqa: BLE001 — a broker outage must never break a stock write
            logger.warning('inventory: could not enqueue back-in-stock for %s: %s', product_id, e)

    transaction.on_commit(_enqueue)
