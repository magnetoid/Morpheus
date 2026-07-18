"""Tree-planting pledge ledger.

One row per order whose shopper opted into the plant-a-tree offset. The store
total shown on the storefront + dashboard is ``SUM(trees)``. The plugin only
*records* what was collected — the merchant fulfils the planting (v1 has no
external reforestation provider). The ``OneToOne`` to Order makes recording
idempotent for free (a second attempt can't create a duplicate row).
"""

from __future__ import annotations

from django.db import models


class TreePledge(models.Model):
    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='eco_tree_pledge',
    )
    # Denormalised so the ledger survives an order hard-delete for reporting,
    # and so the idempotency guard can key on a stable string.
    order_number = models.CharField(max_length=64, db_index=True)
    trees = models.PositiveIntegerField(default=1)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Tree pledge'
        verbose_name_plural = 'Tree pledges'

    def __str__(self) -> str:
        return f'{self.trees} tree(s) — order {self.order_number}'
