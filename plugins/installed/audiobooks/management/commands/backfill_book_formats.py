"""Turn every book that ships a PDF into an *audiobook-on-demand* product.

For each book ``Product`` with a ``digital_file`` (PDF), idempotently:

  * ensure an **E-book** digital ``ProductVariant`` carrying that PDF (a real,
    sellable ebook format in the PDP edition picker), and
  * ensure the **Audiobook** edition exists and point its ``source_pdf`` at the
    same PDF — the on-demand narration source. No audio is generated here;
    staff (or a later step) trigger ElevenLabs from the product form.

Both the ebook variant and the audiobook source *reference the already-stored
PDF* (FileField path reuse) rather than duplicating the file in storage.

Idempotent — safe to re-run; updates in place, never duplicates a variant.

    python manage.py backfill_book_formats --dry-run
    python manage.py backfill_book_formats --limit 50
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Create E-book + Audiobook(on-demand) editions from each book PDF.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would change without writing anything.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Process at most N products (0 = all).',
        )

    def handle(self, *args, **options):
        from plugins.installed.audiobooks.models import Audiobook
        from plugins.installed.catalog.models import Product, ProductVariant

        dry = options['dry_run']
        limit = options['limit']

        qs = (
            Product.objects.filter(book__isnull=False)
            .exclude(digital_file='')
            .exclude(digital_file__isnull=True)
            .order_by('id')
        )
        if limit:
            qs = qs[:limit]

        ebooks = audiobooks = 0
        for product in qs.iterator():
            pdf_name = product.digital_file.name
            base = (product.sku or str(product.id))[:90]

            if dry:
                self.stdout.write(f'  would set up: {product.name!r} (PDF {pdf_name})')
                ebooks += 1
                audiobooks += 1
                continue

            with transaction.atomic():
                # 1. E-book variant referencing the same PDF.
                ebook, _ = ProductVariant.objects.get_or_create(
                    product=product,
                    name='E-book',
                    defaults={
                        'sku': f'{base}-EBOOK',
                        'variant_type': 'digital',
                        'requires_shipping': False,
                    },
                )
                if not ebook.digital_file:
                    ebook.digital_file.name = pdf_name
                    ebook.variant_type = 'digital'
                    ebook.requires_shipping = False
                    ebook.save(update_fields=['digital_file', 'variant_type', 'requires_shipping'])
                ebooks += 1

                # 2. Audiobook edition + narration source.
                ab = (
                    Audiobook.objects.filter(variant__product=product)
                    .select_related('variant')
                    .first()
                )
                if ab is None:
                    variant = ProductVariant.objects.create(
                        product=product,
                        name='Audiobook',
                        sku=f'{base}-AUDIO',
                        variant_type='digital',
                        requires_shipping=False,
                    )
                    ab = Audiobook.objects.create(variant=variant)
                if not ab.source_pdf:
                    ab.source_pdf.name = pdf_name
                    ab.save(update_fields=['source_pdf', 'updated_at'])
                audiobooks += 1

        verb = 'Would create/update' if dry else 'Created/updated'
        self.stdout.write(
            self.style.SUCCESS(
                f'{verb} {ebooks} e-book variant(s) and {audiobooks} audiobook edition(s).'
            )
        )
