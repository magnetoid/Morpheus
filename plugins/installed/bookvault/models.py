"""Bookvault integration — print-on-demand book fulfillment.

Two tracking rows mirror the WP plugin's per-product / per-order meta:

  BookvaultProductLink → which BV print centres fulfil a given product
                         (UK=1, US=3, AU=5, CA=6 in the BV taxonomy) +
                         whether the product is `linked` (linked means
                         BV has matched it to a BV title-and-cover).

  BookvaultOrderLink   → the `BVRef` BV returns when we POST an order;
                         used both for the admin "View on BookVault"
                         deep link and for idempotency on resend.

Credentials (Token, StoreID, Authenticated) live in
`PluginConfig['bookvault'].config` so they're managed through the same
settings panel as every other plugin — no separate model for a single
credential row.
"""

from __future__ import annotations

import uuid

from django.db import models

# BV uses small integer location IDs in their API. Keeping them as
# constants here so views/templates don't repeat literal IDs.
BV_LOCATION_UK = 1
BV_LOCATION_US = 3
BV_LOCATION_AU = 5
BV_LOCATION_CA = 6

BV_LOCATION_CHOICES = (
    (BV_LOCATION_UK, 'Bookvault UK'),
    (BV_LOCATION_US, 'Bookvault US'),
    (BV_LOCATION_AU, 'Bookvault AU'),
    (BV_LOCATION_CA, 'Bookvault CA'),
)


class BookvaultProductLink(models.Model):
    """Per-product (and per-variant) BV linkage record.

    One row per ``(product, variant)`` pair — when ``variant`` is null
    the row refers to the parent product (simple/digital). The BV
    hosted Bulk-Products UI writes back here via webhook with the
    location list + linked flag once the merchant maps the product
    SKU to a BV title.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='bookvault_links',
    )
    variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.CASCADE,
        related_name='bookvault_links',
        null=True,
        blank=True,
    )
    # JSON list of BV location IDs (e.g. [1, 3] = UK + US fulfilment).
    # Empty means "not yet configured at BV"; a non-empty list with
    # is_linked=False means "BV knows the product but hasn't finalised
    # the cover/interior PDF link".
    locations = models.JSONField(default=list, blank=True)
    is_linked = models.BooleanField(
        default=False,
        help_text='True once BV has matched this product to a BV title.',
    )
    # BV's internal identifier for the linked title, when present.
    bv_title_id = models.CharField(max_length=64, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'variant')
        indexes = [
            models.Index(fields=['product', 'is_linked']),
        ]

    def __str__(self) -> str:
        target = self.variant.sku if self.variant_id else self.product.slug
        return f'BV link · {target} · {"linked" if self.is_linked else "pending"}'


class BookvaultOrderLink(models.Model):
    """Per-order BV reference.

    Created the first time we POST the order to BV's
    /woocommerce/orders/create endpoint. ``bv_ref`` is BV's order
    number — used for the "View on BookVault" portal link and to make
    a resend idempotent (the row's mere presence tells us BV already
    saw this order)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='bookvault_link',
    )
    bv_ref = models.CharField(max_length=64, blank=True, default='')
    # Last response from BV — useful when the POST succeeded HTTP-wise
    # but BV returned a structured error we want to surface.
    last_response = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    last_sent_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f'BV order · {self.order_id} · {self.bv_ref or "(no ref)"}'
