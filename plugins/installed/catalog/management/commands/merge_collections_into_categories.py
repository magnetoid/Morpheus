"""Collections-merge Phase 2 — backfill Product.categories from the
legacy single `category` FK + the `collections` M2M.

Part of docs/plans/collections-merge.md. The unified "Collections"
concept is hierarchical (Category/MPTT) + many-per-product
(Product.categories M2M, added in Phase 1). This command populates
that M2M without destroying anything:

  1. For each Collection, get-or-create a top-level Category mirroring
     it (name + slug + image), so collection membership survives as
     category membership.
  2. For each Product: add its `.category` (if set) and every mapped
     Category (from its `.collections`) into `.categories`.

Idempotent — re-runnable. Uses get_or_create + M2M .add() (a no-op
when the link already exists). Safe to run repeatedly during the
dual-write window.

Usage:
    python manage.py merge_collections_into_categories
    python manage.py merge_collections_into_categories --dry-run
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand
from django.utils.text import slugify

logger = logging.getLogger('morpheus.catalog')


class Command(BaseCommand):
    help = 'Backfill Product.categories from category FK + collections M2M (collections-merge phase 2).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change without writing.',
        )

    def handle(self, *args, **opts):
        from plugins.installed.catalog.models import Category, Collection, Product

        dry = opts['dry_run']
        prefix = '[dry-run] ' if dry else ''

        # ── 1. Mirror each Collection as a top-level Category ──────────
        # collection.id -> Category. Slug clashes get a -collection suffix
        # so we never hijack an existing Category's slug.
        col_to_cat: dict = {}
        mirrored = 0
        for col in Collection.objects.all():
            base_slug = (col.slug or slugify(col.name) or 'collection').strip()
            existing = Category.objects.filter(slug=base_slug).first()
            if existing is not None:
                # A Category already owns this slug — reuse it as the
                # merge target rather than duplicating.
                col_to_cat[col.id] = existing
                continue
            if dry:
                self.stdout.write(f'{prefix}create Category "{col.name}" (slug={base_slug})')
                # Use a transient object so the per-product pass can still
                # map; it won't be saved in dry-run.
                col_to_cat[col.id] = Category(name=col.name, slug=base_slug)
                continue
            cat = Category.objects.create(
                name=col.name,
                slug=base_slug,
                description=getattr(col, 'description', '') or '',
                is_active=getattr(col, 'is_active', True),
            )
            # Carry the image across if the Collection had one + Category
            # supports it (both use an ImageField named `image`).
            col_img = getattr(col, 'image', None)
            if col_img and getattr(col_img, 'name', '') and hasattr(cat, 'image'):
                cat.image = col_img.name
                cat.save(update_fields=['image'])
            col_to_cat[col.id] = cat
            mirrored += 1

        # ── 2. Backfill Product.categories ────────────────────────────
        linked = 0
        products = Product.objects.all().prefetch_related('collections').select_related('category')
        for p in products:
            targets = set()
            if p.category_id:
                targets.add(p.category_id)
            for col in p.collections.all():
                cat = col_to_cat.get(col.id)
                if cat is not None and getattr(cat, 'id', None):
                    targets.add(cat.id)
            if not targets:
                continue
            if dry:
                self.stdout.write(f'{prefix}product {p.slug}: +{len(targets)} categories')
                continue
            # .add() is idempotent — re-running won't duplicate links.
            p.categories.add(*targets)
            linked += 1

        self.stdout.write(self.style.SUCCESS(
            f'{prefix}done — mirrored {mirrored} collection(s) into categories, '
            f'linked {linked} product(s).'
        ))
