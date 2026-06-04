"""Repair auto-filled SeoMeta titles that baked in a stale brand suffix.

Historically ``autofill_meta_for`` stored ``"{name} — {STORE_NAME}"`` (env
default "Morpheus Store") into ``SeoMeta.title``. Titles are now stored clean
(just the page name) and the brand is applied at render via the settings
``title_template``. This command rewrites existing auto-filled rows to the
clean page name so they pick up the configured brand. Merchant-edited rows
(``auto_filled=False``) are left untouched.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from plugins.installed.seo.models import SeoMeta


class Command(BaseCommand):
    help = 'Rewrite auto-filled SeoMeta titles to the clean page name (drops stale brand suffix).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true', help='Report what would change without writing.'
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        changed = skipped = 0
        for meta in SeoMeta.objects.filter(auto_filled=True).iterator():
            obj = meta.target
            name = (getattr(obj, 'name', '') or '').strip() if obj is not None else ''
            if not name or meta.title == name:
                skipped += 1
                continue
            self.stdout.write(f'  {meta.title!r} → {name!r}')
            if not dry:
                meta.title = name
                meta.save(update_fields=['title'])
            changed += 1
        verb = 'would rewrite' if dry else 'rewrote'
        self.stdout.write(
            self.style.SUCCESS(f'{verb} {changed} title(s); {skipped} already clean.')
        )
