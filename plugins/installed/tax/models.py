"""Tax models — regions and rates.

Designed to handle three common cases:

1. **Single-flat-rate** (default): one `TaxRate` for `country=*, region=*` with
   merchant's nominal rate. Smallest setup.
2. **US sales tax by state**: `TaxRate` per `country=US, region=<state>`.
3. **EU VAT / OSS**: `TaxRate` per EU country, optionally with category-specific
   reduced rates via `TaxCategory`.

A future Stripe Tax adapter can replace the local lookup by setting
`TaxConfiguration.provider='stripe'` and reading rates from the API.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from morpheus import models


class TaxCategory(models.Model):
    """Reduced-rate categories (e.g. books, food, children's clothing).

    Products link via `Product.tax_category_code` (string match) so we don't
    introduce an FK from the catalog plugin into tax. Loose coupling.
    """

    code = models.SlugField(primary_key=True, max_length=64)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class TaxRegion(models.Model):
    """A taxable region — typically (country, region) pair.

    `region` is empty for whole-country rules, set for sub-national
    (US states, Canadian provinces, etc.).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    country = models.CharField(max_length=2, help_text='ISO-3166 alpha-2 code, e.g. US')
    region = models.CharField(max_length=10, blank=True, help_text='Subdivision code, e.g. CA, NY')
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ['country', 'region', 'name']
        unique_together = ('country', 'region')

    def __str__(self) -> str:
        return f'{self.country}{("-" + self.region) if self.region else ""} ({self.name})'


class TaxRate(models.Model):
    """A tax rate scoped to (region × optional category)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, help_text='Display name (e.g. "VAT 20%")')
    region = models.ForeignKey(TaxRegion, on_delete=models.CASCADE, related_name='rates')
    category = models.ForeignKey(
        TaxCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rates',
        help_text='Leave blank for the default rate in this region.',
    )
    rate_percent = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        help_text='Percent — 8.875 means 8.875%',
    )
    is_compound = models.BooleanField(default=False)
    priority = models.PositiveSmallIntegerField(
        default=0,
        help_text='Lower = applied first; matters when is_compound=True.',
    )

    class Meta:
        ordering = ['region', 'priority', 'category']

    def __str__(self) -> str:
        return f'{self.name} ({self.rate_percent}%)'

    @property
    def fraction(self) -> Decimal:
        return Decimal(self.rate_percent) / Decimal(100)


class TaxConfiguration(models.Model):
    """Singleton-style configuration row."""

    PROVIDER_CHOICES = [
        ('local', 'Local rates'),
        ('stripe', 'Stripe Tax'),
        ('none', 'No tax'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=10, choices=PROVIDER_CHOICES, default='local')
    prices_include_tax = models.BooleanField(
        default=False,
        help_text='If True, product prices already include tax (EU pattern).',
    )
    default_region = models.ForeignKey(
        TaxRegion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Used when no shipping address is available.',
    )
    updated_at = models.DateTimeField(auto_now=True)
