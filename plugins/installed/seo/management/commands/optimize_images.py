"""Pre-generate (warm) WebP/AVIF variants for existing images.

The "optimize old images" batch action. Purely additive + idempotent:
it writes only under ``MEDIA_ROOT/seo_img_cache/`` (exactly where the
``/img/<fmt>/<width>/<path>`` view reads), and never touches originals,
models, or the upload path. Safe to re-run; a second pass regenerates
nothing.

    manage.py optimize_images                 # webp at 400/800/1200
    manage.py optimize_images --avif          # also avif (slower)
    manage.py optimize_images --widths 400,800,1200,1600
    manage.py optimize_images --dry-run       # report only, no writes
"""

# ruff: noqa: PLC0415 — catalog/media model imports are lazy (optional plugins).
from __future__ import annotations

import os

from django.conf import settings
from django.core.management.base import BaseCommand

from plugins.installed.seo.services.images import (
    ALLOWED_IMAGE_WIDTHS,
    generate_image_variant,
    variant_cache_abs,
)

DEFAULT_WIDTHS = (400, 800, 1200)


class Command(BaseCommand):
    help = 'Pre-generate WebP/AVIF variants for existing product + media images (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--widths',
            default=','.join(str(w) for w in DEFAULT_WIDTHS),
            help=f'Comma-separated widths, subset of {ALLOWED_IMAGE_WIDTHS}.',
        )
        parser.add_argument('--avif', action='store_true', help='Also generate AVIF (slower).')
        parser.add_argument('--limit', type=int, default=0, help='Max source images (0 = all).')
        parser.add_argument('--dry-run', action='store_true', help='Report work without writing.')

    def handle(self, *args, **opts):
        widths = [
            int(w)
            for w in str(opts['widths']).split(',')
            if w.strip().isdigit() and int(w) in ALLOWED_IMAGE_WIDTHS
        ]
        if not widths:
            self.stderr.write(f'No valid widths given (allowed: {ALLOWED_IMAGE_WIDTHS}).')
            return
        fmts = ['webp'] + (['avif'] if opts['avif'] else [])
        dry = opts['dry_run']
        media_root = str(settings.MEDIA_ROOT)

        rels = self._source_rels(opts['limit'] or 0)
        generated = skipped = missing = errors = 0
        bytes_written = 0

        for rel in rels:
            src_abs = os.path.join(media_root, rel)
            if not os.path.isfile(src_abs):
                missing += 1
                continue
            for width in widths:
                for fmt in fmts:
                    cache_abs = variant_cache_abs(rel, width, fmt)
                    if os.path.isfile(cache_abs):
                        skipped += 1
                        continue
                    if dry:
                        generated += 1
                        continue
                    try:
                        generate_image_variant(src_abs, cache_abs, width=width, fmt=fmt)
                        generated += 1
                        if os.path.isfile(cache_abs):
                            bytes_written += os.path.getsize(cache_abs)
                    except Exception as e:  # noqa: BLE001 — one bad image must not abort the batch
                        errors += 1
                        self.stderr.write(f'  ! {rel} w{width} {fmt}: {e}')

        verb = 'would generate' if dry else 'generated'
        self.stdout.write(
            self.style.SUCCESS(
                f'{len(rels)} source images · {verb} {generated} variants · '
                f'{skipped} already cached · {missing} missing files · {errors} errors · '
                f'{bytes_written / (1024 * 1024):.1f} MB written'
            )
        )

    def _source_rels(self, limit: int) -> list[str]:
        """Storage-relative paths of every product + media-library image."""
        rels: list[str] = []
        try:
            from plugins.installed.catalog.models import ProductImage

            rels.extend(
                str(n)
                for n in ProductImage.objects.exclude(image='').values_list('image', flat=True)
                if n
            )
        except Exception as e:  # noqa: BLE001 — catalog may be unavailable
            self.stderr.write(f'catalog images skipped: {e}')
        try:
            from plugins.installed.media.models import MediaAsset

            rels.extend(
                str(n)
                for n in MediaAsset.objects.filter(kind='image')
                .exclude(file='')
                .values_list('file', flat=True)
                if n
            )
        except Exception as e:  # noqa: BLE001 — media may be unavailable
            self.stderr.write(f'media images skipped: {e}')

        seen: set[str] = set()
        uniq: list[str] = []
        for r in rels:
            if r not in seen:
                seen.add(r)
                uniq.append(r)
        return uniq[:limit] if limit and limit > 0 else uniq
