"""Shipping models — zones, rates, free-shipping rules.

`ShippingZone` is a set of countries (and optional region codes) that share
shipping rules. A `ShippingRate` belongs to a zone and computes a price
based on either flat fee, weight tiers, or order-total tiers.

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
