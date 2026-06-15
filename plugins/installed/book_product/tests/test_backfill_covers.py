"""backfill_book_covers — styled cover generation + idempotent apply."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from django.core.management import call_command
from django.test import TestCase
from djmoney.money import Money
from PIL import Image

from plugins.installed.book_product.management.commands.backfill_book_covers import (
    render_cover_bytes,
)
from plugins.installed.book_product.models import BookProduct, Genre
from plugins.installed.catalog.models import Product


def _book(slug, sku, **bp):
    p = Product.objects.create(
        name=slug.replace('-', ' ').title(),
        slug=slug,
        sku=sku,
        price=Money(Decimal('9.00'), 'USD'),
        product_type='simple',
        status='active',
    )
    BookProduct.objects.create(product=p, **bp)
    return p


class RenderCoverTests(TestCase):
    def test_renders_valid_jpeg_at_expected_size(self):
        data = render_cover_bytes(
            title='Moby-Dick', author='Herman Melville', genre='Adventure', slug='moby-dick'
        )
        img = Image.open(BytesIO(data))
        self.assertEqual(img.format, 'JPEG')
        self.assertEqual(img.size, (800, 1200))

    def test_handles_empty_author_and_genre(self):
        data = render_cover_bytes(title='Untitled', slug='x')
        self.assertEqual(Image.open(BytesIO(data)).size, (800, 1200))

    def test_colour_is_deterministic_for_slug(self):
        a = render_cover_bytes(title='A', slug='same-slug')
        b = render_cover_bytes(title='A', slug='same-slug')
        self.assertEqual(a, b)


class BackfillCommandTests(TestCase):
    def test_dry_run_writes_nothing(self):
        p = _book('the-quiet-hour', 'BK1', author='A. Writer')
        call_command('backfill_book_covers')  # no --apply
        self.assertFalse(p.images.exists())

    def test_apply_creates_primary_image_and_og(self):
        g = Genre.objects.create(name='Fiction', slug='fiction')
        p = _book('dune', 'BK2', author='Frank Herbert')
        p.book.genres.add(g)

        call_command('backfill_book_covers', '--apply')

        p.refresh_from_db()
        img = p.images.filter(is_primary=True).first()
        self.assertIsNotNone(img)
        self.assertTrue(img.image)
        self.assertTrue(p.og_image)

    def test_apply_is_idempotent_and_skips_imaged_books(self):
        p = _book('already', 'BK3')
        call_command('backfill_book_covers', '--apply')
        self.assertEqual(p.images.count(), 1)
        # Second run must not add a second cover.
        call_command('backfill_book_covers', '--apply')
        self.assertEqual(p.images.count(), 1)
