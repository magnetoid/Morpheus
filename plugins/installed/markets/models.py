"""Market + ProductMarketPrice — per-region pricing primitives."""
from __future__ import annotations

import uuid

from django.db import models
from djmoney.models.fields import MoneyField


class Market(models.Model):
    """A logical sales region.

    A market binds a set of countries to a currency, a default locale,
    and a price adjustment. Resolution at request time:
      1. Explicit `?market=<code>` query param wins.
      2. Else first market whose `country_codes` contains the visitor's
         country (from `CF-IPCountry` header by default).
      3. Else the market flagged `is_default=True`.
      4. Else None — caller falls back to channel default.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(
        max_length=40, unique=True,
        help_text='Stable identifier — used in URLs and per-product price overrides.',
    )
    label = models.CharField(max_length=120)
    country_codes = models.JSONField(
        default=list, blank=True,
        help_text='List of ISO 3166-1 alpha-2 country codes (e.g. ["US", "CA"]).',
    )
    currency = models.CharField(
        max_length=3, default='USD',
        help_text='ISO 4217 currency code prices in this market are quoted in.',
    )
    default_locale = models.CharField(
        max_length=10, default='en',
        help_text='Locale code for storefront translations (e.g. "en", "en-GB", "fr").',
    )
    base_price_adjustment_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        help_text=(
            'Whole-catalog price multiplier vs the channel base, in %. '
            'e.g. 10 = +10% in this market. Per-product overrides in '
            'ProductMarketPrice take precedence.'
        ),
    )
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text='Fallback when no country match is found.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['label']

    def __str__(self) -> str:
        return f'{self.label} ({self.code}, {self.currency})'

    @property
    def country_set(self) -> set[str]:
        return {c.strip().upper() for c in (self.country_codes or []) if c}


class ProductMarketPrice(models.Model):
    """Per-product price override for a single market.

    Mirrors `catalog.ProductChannelListing` shape but scoped to a
    market. Optional: when no row exists for a (product, market)
    pair, the resolution chain falls through to the market's
    `base_price_adjustment_pct`, then to the channel listing, then
    to `Product.price`.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    market = models.ForeignKey(
        Market, on_delete=models.CASCADE, related_name='product_prices',
    )
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.CASCADE,
        related_name='market_prices',
    )
    price = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    is_visible = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('market', 'product')]
        indexes = [
            models.Index(fields=['market', 'product']),
        ]
        ordering = ['market', 'product']

    def __str__(self) -> str:
        return f'{self.product} @ {self.market.code} = {self.price}'
