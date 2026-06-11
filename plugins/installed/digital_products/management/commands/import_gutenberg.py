"""Attach Project Gutenberg plain-text files to existing products.

Discovery: any Product whose primary image filename matches
``gutenberg-<N>.<ext>`` already has Gutenberg metadata + a cover —
this command just downloads the body text, strips Gutenberg's
boilerplate, and stores it in ``product.digital_file`` so the
customer can download the book after purchase.

Idempotent: skips products that already have ``digital_file`` set.
Pass --force to re-download.

Usage:
    python manage.py import_gutenberg
    python manage.py import_gutenberg --slugs pinocchio,anna-karenina
    python manage.py import_gutenberg --force
"""

from __future__ import annotations

import logging
import re

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

logger = logging.getLogger('morpheus.gutenberg')


_START_RE = re.compile(
    r'^\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG (?:EBOOK|EBook).*?\*\*\*',
    re.MULTILINE | re.IGNORECASE,
)
_END_RE = re.compile(
    r'^\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG (?:EBOOK|EBook).*?\*\*\*',
    re.MULTILINE | re.IGNORECASE,
)


def strip_gutenberg_boilerplate(raw: str) -> str:
    """Remove Project Gutenberg's licence header + footer.

    Project Gutenberg wraps every plain-text book in two sentinel
    lines. Everything before START and after END is the licence,
    metadata, transcriber notes, and credits — not part of the work
    itself. Strip them to give the customer the book they paid for.
    """
    start_match = _START_RE.search(raw)
    end_match = _END_RE.search(raw)
    if start_match and end_match and end_match.start() > start_match.end():
        body = raw[start_match.end() : end_match.start()]
    elif start_match:
        body = raw[start_match.end() :]
    else:
        body = raw
    return body.strip() + '\n'


def _gutenberg_id_from_image_name(name: str) -> int | None:
    if not name:
        return None
    m = re.search(r'gutenberg[-_](\d+)', name, re.IGNORECASE)
    return int(m.group(1)) if m else None


class Command(BaseCommand):
    help = 'Attach Project Gutenberg plain-text files to existing products.'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--slugs',
            default='',
            help='Comma-separated product slugs (default: all gutenberg-tagged products).',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-download even when digital_file is already set.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would happen; do not write any files or save products.',
        )

    def handle(self, *args, **opts) -> None:
        import urllib.request

        from plugins.installed.catalog.models import Product

        slugs = [s.strip() for s in (opts.get('slugs') or '').split(',') if s.strip()]
        force = bool(opts.get('force'))
        dry = bool(opts.get('dry_run'))

        qs = Product.objects.all().prefetch_related('images')
        if slugs:
            qs = qs.filter(slug__in=slugs)

        total = 0
        attached = 0
        skipped = 0
        missing = 0

        for product in qs:
            total += 1
            primary = (
                next(
                    (i for i in product.images.all() if getattr(i, 'is_primary', False)),
                    None,
                )
                or product.images.first()
            )
            image_name = ''
            if primary and getattr(primary, 'image', None):
                image_name = primary.image.name or ''

            gid = _gutenberg_id_from_image_name(image_name) or _gutenberg_id_from_image_name(
                product.slug
            )
            if gid is None:
                continue  # not a Gutenberg-imported title

            if product.digital_file and not force:
                skipped += 1
                self.stdout.write(f'  skip {product.slug} (already has digital_file)')
                continue

            url = f'https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt'
            self.stdout.write(f'→ {product.slug} (gutenberg id {gid})')

            if dry:
                continue

            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'morpheus-import/1.0'})  # noqa: S310
                with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310  # nosec B310
                    raw = resp.read().decode('utf-8', errors='replace')
            except Exception as exc:  # noqa: BLE001
                logger.warning('gutenberg fetch failed for %s (gid=%s): %s', product.slug, gid, exc)
                missing += 1
                continue

            body = strip_gutenberg_boilerplate(raw)
            filename = f'{product.slug}.txt'
            product.digital_file.save(filename, ContentFile(body.encode('utf-8')), save=False)
            if product.product_type != 'digital':
                product.product_type = 'digital'
            product.save(update_fields=['digital_file', 'product_type'])
            attached += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'done — checked={total} attached={attached} skipped={skipped} missing={missing}'
            )
        )
