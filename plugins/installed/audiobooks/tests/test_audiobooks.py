"""Audiobooks plugin tests — model shape + the player-gating property.

Storefront/permission boundary tests land with the PDP player block (phase 3).
"""

# Lazy imports inside tests are intentional (plugin load-order isolation).
# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money


class AudiobookModelTests(TestCase):
    def _audiobook_variant(self):
        from plugins.installed.catalog.models import Product, ProductVariant

        product = Product.objects.create(
            name='Test Book',
            slug='ab-book',
            sku='AB-1',
            status='active',
            price=Money(Decimal('10.00'), 'USD'),
        )
        return ProductVariant.objects.create(
            product=product,
            name='Audiobook',
            sku='AB-1-AUDIO',
            price=Money(Decimal('14.99'), 'USD'),
            variant_type='digital',
            requires_shipping=False,
        )

    def test_is_ready_requires_both_status_and_file(self):
        from plugins.installed.audiobooks.models import Audiobook

        ab = Audiobook.objects.create(variant=self._audiobook_variant(), status='none')
        self.assertFalse(ab.is_ready)
        # status='ready' alone is not enough — there must be an actual file.
        ab.status = 'ready'
        self.assertFalse(ab.is_ready)

    def test_onetoone_to_variant(self):
        from plugins.installed.audiobooks.models import Audiobook

        variant = self._audiobook_variant()
        ab = Audiobook.objects.create(variant=variant, narrator='Jane Doe', source='uploaded')
        self.assertEqual(variant.audiobook, ab)
        self.assertEqual(ab.narrator, 'Jane Doe')
        self.assertEqual(ab.status, 'none')
