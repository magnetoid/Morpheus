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


class ProductFormHandlerTests(TestCase):
    """The PRODUCT_FORM_SAVED handler creates the audiobook EDITION as a real
    digital variant — only for book products."""

    def _book(self):
        from plugins.installed.book_product.models import BookProduct
        from plugins.installed.catalog.models import Product

        product = Product.objects.create(
            name='A Book',
            slug='ab-form',
            sku='ABF-1',
            status='active',
            price=Money(Decimal('9.99'), 'USD'),
        )
        BookProduct.objects.create(product=product, author='An Author')
        return product

    def test_saved_handler_creates_digital_audiobook_variant(self):
        from plugins.installed.audiobooks.models import Audiobook
        from plugins.installed.audiobooks.plugin import AudiobooksPlugin

        product = self._book()
        AudiobooksPlugin().on_product_form_saved(
            product=product,
            post={
                'audiobook_enabled': '1',
                'audiobook_price': '14.99',
                'audiobook_narrator': 'Jane',
            },
            files=None,
        )
        ab = Audiobook.objects.get(variant__product=product)
        self.assertEqual(ab.narrator, 'Jane')
        self.assertEqual(ab.variant.variant_type, 'digital')
        self.assertFalse(ab.variant.requires_shipping)
        self.assertEqual(str(ab.variant.price.amount), '14.99')

    def test_non_book_product_is_ignored(self):
        # No BookProduct → product.book raises (AttributeError subclass) → the
        # guard returns cleanly and no audiobook variant is created.
        from plugins.installed.audiobooks.models import Audiobook
        from plugins.installed.audiobooks.plugin import AudiobooksPlugin
        from plugins.installed.catalog.models import Product

        mug = Product.objects.create(
            name='Mug',
            slug='ab-mug',
            sku='ABM-1',
            status='active',
            price=Money(Decimal('5.00'), 'USD'),
        )
        AudiobooksPlugin().on_product_form_saved(
            product=mug, post={'audiobook_enabled': '1'}, files=None
        )
        self.assertFalse(Audiobook.objects.filter(variant__product=mug).exists())
