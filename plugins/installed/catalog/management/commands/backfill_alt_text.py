"""Backfill content-aware alt text on ProductImage rows.

The SEO audit penalises three alt-text shapes: empty, generic (image
/ photo / cover), and "alt equals product name" (duplicate_alt — which
flagged 37 of 50 products on our last run). For book covers we can
construct a deterministic, content-aware alt from data we already
have on disk: ``"{title} by {author} — book cover"`` for the primary
image, and ``"{title} — back cover"`` / ``"{title} — interior page"``
for non-primary slides.

Idempotent: skips images whose alt is already non-empty AND not equal
to the product name AND not in the generic set. Pass ``--force`` to
overwrite even good-looking values.

Usage:
    python manage.py backfill_alt_text
    python manage.py backfill_alt_text --slugs hamlet,dracula --force --dry-run
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger('morpheus.catalog')

_GENERIC = {'image', 'photo', 'picture', 'cover', 'product image', 'book cover'}


def _build_alt(product, image, *, author: str) -> str:
    """Compose a content-aware alt string for one image."""
    title = (product.name or '').strip()
    if not title:
        # No name to work with — at least describe what it is.
        return 'Book cover'
    if image.sort_order == 0 and image.is_primary:
        return f'{title} by {author} — book cover' if author else f'{title} — book cover'
    if image.sort_order == 1 and image.is_primary:
        return f'{title} — back cover'
    return f'{title} — interior page {image.sort_order}'


class Command(BaseCommand):
    help = 'Backfill content-aware ProductImage.alt_text for book covers.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--slugs', default='', help='Comma-separated product slugs (default: all active).'
        )
        parser.add_argument(
            '--force', action='store_true', help='Overwrite even when current alt looks acceptable.'
        )
        parser.add_argument(
            '--dry-run', action='store_true', help='Show what would change; do not write.'
        )

    def handle(self, *args, **opts):
        from django.contrib.contenttypes.models import ContentType

        from plugins.installed.catalog.models import Product
        from plugins.installed.metafields.models import Metafield

        slugs = [s.strip() for s in (opts.get('slugs') or '').split(',') if s.strip()]
        force = bool(opts['force'])
        dry = bool(opts['dry_run'])

        qs = Product.objects.filter(status='active').prefetch_related('images')
        if slugs:
            qs = qs.filter(slug__in=slugs)

        ct = ContentType.objects.get_for_model(Product)
        authors = {
            m.object_id: (m.value or '').strip()
            for m in Metafield.objects.filter(
                content_type=ct,
                namespace='book',
                key='author',
            )
        }

        updated = skipped = 0
        for product in qs:
            author = authors.get(str(product.pk), '')
            name_lower = (product.name or '').strip().lower()
            for image in product.images.all():
                current = (image.alt_text or '').strip()
                current_lower = current.lower()
                acceptable = (
                    current
                    and current_lower != name_lower
                    and current_lower not in _GENERIC
                    and len(current) >= 8
                )
                if acceptable and not force:
                    skipped += 1
                    continue
                new_alt = _build_alt(product, image, author=author)
                if new_alt == current:
                    skipped += 1
                    continue
                self.stdout.write(f'  {product.slug}#{image.sort_order}: {current!r} → {new_alt!r}')
                if dry:
                    continue
                image.alt_text = new_alt
                image.save(update_fields=['alt_text'])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f'done — updated={updated} skipped={skipped}'))
