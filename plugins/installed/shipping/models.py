"""Shipping models — zones, rates, free-shipping rules.

`ShippingZone` is a set of countries (and optional region codes) that share
shipping rules. A `ShippingRate` belongs to a zone and computes a price
based on either flat fee, weight tiers, order-total tiers, a free-over
threshold, or a pickup (the customer collects it; free or a flat fee).
Amounts are in the store's currency (`shipping/rates.py`).

Carrier integrations (Shippo / EasyPost) plug in via
`ShippingRate.computation = 'carrier_<name>'`; the rate runs the adapter
at quote time. Adapters live in `plugins.installed.shipping.carriers`.
"""

from __future__ import annotations

import uuid

from djmoney.models.fields import MoneyField

from morpheus.app import models


class ShippingZone(models.Model):
    """Geographic group of destinations that share rules."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    countries = models.JSONField(
        default=list,
        help_text='List of ISO-3166 alpha-2 country codes. ["*"] = catch-all.',
    )
    regions = models.JSONField(
        default=list,
        blank=True,
        help_text='Optional sub-national filter; e.g. ["CA","NY"] for US states.',
    )
    is_default = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        countries = ','.join(self.countries[:3])
        if len(self.countries) > 3:
            countries += '…'
        return f'{self.name} ({countries})'

    def matches(self, country: str, region: str = '') -> bool:
        country = (country or '').strip().upper()[:2]
        region = (region or '').strip().upper()[:10]
        if not country:
            return self.is_default
        if '*' in self.countries:
            return True
        if country not in [c.upper() for c in self.countries]:
            return False
        if self.regions and region:
            return region in [r.upper() for r in self.regions]
        return True


class ShippingRate(models.Model):
    """A purchasable shipping option within a zone."""

    COMPUTATION_CHOICES = [
        ('flat', 'Flat fee'),
        ('weight_tier', 'Weight tiered'),
        ('order_total_tier', 'Order-total tiered'),
        ('free_over', 'Free over threshold'),
        ('pickup', 'Pickup (the customer collects it)'),
        ('carrier_shippo', 'Shippo (live rates)'),
        ('carrier_easypost', 'EasyPost (live rates)'),
        ('carrier_bookvault', 'Bookvault (live rates · POD books)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(ShippingZone, on_delete=models.CASCADE, related_name='rates')
    name = models.CharField(max_length=120, help_text='e.g. "Standard ground", "Express overnight"')
    description = models.CharField(max_length=240, blank=True)
    computation = models.CharField(max_length=20, choices=COMPUTATION_CHOICES, default='flat')

    flat_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='USD',
        null=True,
        blank=True,
    )
    free_threshold = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='USD',
        null=True,
        blank=True,
        help_text='If subtotal ≥ this, the rate is free (used by free_over).',
    )
    tiers = models.JSONField(
        default=list,
        blank=True,
        help_text='List of {threshold, amount} for tiered modes (sorted ascending).',
    )
    estimated_days_min = models.PositiveSmallIntegerField(null=True, blank=True)
    estimated_days_max = models.PositiveSmallIntegerField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    priority = models.PositiveSmallIntegerField(default=50, help_text='Lower = shown first.')

    class Meta:
        ordering = ['zone', 'priority', 'name']

    def __str__(self) -> str:
        return f'{self.zone.name} · {self.name}'


class ShippingLabel(models.Model):
    """A carrier label for an order's parcel (``shipping/labels.py``).

    The row is written before the carrier is asked (*purchasing*), so a second
    click finds it and a label the carrier charged for is never lost. *bought*
    holds the carrier's answer; *unconfirmed* means the carrier was asked to buy
    and its answer did not say whether it did, so the merchant checks their
    carrier account. ``fulfillment`` is empty for a label bought for every open
    unit until its parcel is recorded, for one whose parcel could not be
    recorded, and for an unconfirmed one (so the parcel can be tried again).
    """

    PROVIDER_CHOICES = [('shippo', 'Shippo'), ('easypost', 'EasyPost')]
    STATUS_CHOICES = [
        ('purchasing', 'Being bought'),
        ('bought', 'Bought'),
        ('unconfirmed', 'Not confirmed by the carrier'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        'orders.Order', on_delete=models.CASCADE, related_name='shipping_labels'
    )
    fulfillment = models.OneToOneField(
        'orders.Fulfillment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shipping_label',
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='purchasing')
    provider_id = models.CharField(
        max_length=120, blank=True, help_text="The carrier service's label id."
    )
    label_url = models.URLField(max_length=1000, blank=True)
    tracking_number = models.CharField(max_length=200, blank=True)
    tracking_url = models.URLField(max_length=1000, blank=True)
    carrier = models.CharField(max_length=100, blank=True)
    service = models.CharField(max_length=120, blank=True)
    cost_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    cost_currency = models.CharField(max_length=3, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.get_provider_display()} label {self.tracking_number or self.provider_id}'
