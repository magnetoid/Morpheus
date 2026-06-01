"""Find (and optionally delete) products whose slug is a Django
uniqueness-suffixed duplicate — e.g. ``utopia-1`` / ``utopia-2`` sitting
alongside a canonical ``utopia``. When two products are saved with the
same name, Django appends ``-1``, ``-2``… to keep the slug unique; those
suffixed rows are usually accidental re-imports.

DRY-RUN by default. Pass ``--delete`` to actually remove the verified
duplicates.

A suffixed product is treated as a deletable duplicate ONLY when ALL hold:
  * its slug matches ``<base>-<n>`` where ``1 <= n <= --max-suffix`` (default 4),
  * a canonical product with slug == ``<base>`` exists,
  * it shares the canonical product's name (case-insensitive),
  * it has NO order history (no OrderItem rows).

Those rules filter out legitimate slugs like ``volume-1`` / ``part-2``
(no base sibling) and protect anything that was actually sold (reported,
never deleted, so historical order references survive). Always run the
default dry-run first and eyeball the list before ``--delete``.
"""

# ruff: noqa: PLC0415, PLR0912
# Inline imports keep the command import-light + avoid app-loading order
# issues; the branchy handle() is a deliberate report-then-act flow.

from __future__ import annotations

import re

from django.core.management.base import BaseCommand
from django.db import transaction

SUFFIX_RE = re.compile(r'^(?P<base>.+)-(?P<n>\d+)$')


class Command(BaseCommand):
    help = 'Remove Django slug-uniqueness duplicate products (slug ending -1 .. -N).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Actually delete the duplicates. Without this flag it is a dry-run.',
        )
        parser.add_argument(
            '--max-suffix',
            type=int,
            default=4,
            help='Only consider slugs ending -1 .. -N (default 4).',
        )

    def handle(self, *args, **opts):
        from plugins.installed.catalog.models import Product
        from plugins.installed.orders.models import OrderItem

        do_delete = opts['delete']
        max_suffix = opts['max_suffix']
        w = self.stdout.write

        by_slug = {p.slug: p for p in Product.objects.all().only('id', 'slug', 'name', 'status')}
        candidates = []  # (dup, canonical) — safe to delete
        skipped_sold = []  # (dup, canonical) — has order history
        skipped_no_base = []  # dup — no canonical sibling (likely legit)
        skipped_name = []  # (dup, canonical) — name differs

        for slug, p in by_slug.items():
            m = SUFFIX_RE.match(slug)
            if not m:
                continue
            n = int(m.group('n'))
            if n < 1 or n > max_suffix:
                continue
            canonical = by_slug.get(m.group('base'))
            if canonical is None:
                skipped_no_base.append(p)
            elif (p.name or '').strip().lower() != (canonical.name or '').strip().lower():
                skipped_name.append((p, canonical))
            elif OrderItem.objects.filter(product=p).exists():
                skipped_sold.append((p, canonical))
            else:
                candidates.append((p, canonical))

        w(f'Scanned {len(by_slug)} products. Suffix window: -1 .. -{max_suffix}.')
        w(self.style.WARNING(f'Duplicates safe to delete: {len(candidates)}'))
        for dup, canon in candidates:
            w(f'  DELETE  {dup.slug}  (dup of {canon.slug}) — "{dup.name}"')
        if skipped_sold:
            w(f'KEEP — has order history, review manually: {len(skipped_sold)}')
            for dup, canon in skipped_sold:
                w(f'  KEEP    {dup.slug}  (dup of {canon.slug}) — sold')
        if skipped_no_base:
            w(
                f'KEEP — no canonical base slug (likely legit, e.g. volume-1): {len(skipped_no_base)}'
            )
            for p in skipped_no_base:
                w(f'  KEEP    {p.slug}')
        if skipped_name:
            w(f'KEEP — name differs from canonical, not a clear dup: {len(skipped_name)}')
            for dup, canon in skipped_name:
                w(f'  KEEP    {dup.slug}  (base {canon.slug}) — "{dup.name}" != "{canon.name}"')

        if not do_delete:
            w('')
            w(
                'DRY-RUN — nothing deleted. Re-run with --delete to remove the '
                f'{len(candidates)} duplicate(s) listed above.'
            )
            return

        with transaction.atomic():
            ids = [dup.id for dup, _ in candidates]
            deleted, _ = Product.objects.filter(id__in=ids).delete()
        w(
            self.style.SUCCESS(
                f'Deleted {len(candidates)} duplicate products ({deleted} rows total).'
            )
        )
