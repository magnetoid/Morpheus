"""
Convert product long descriptions from markdown to HTML.

After we switched the admin product form to a TipTap WYSIWYG editor
(which stores HTML), the 50 LLM-enriched descriptions stored as
Markdown need to be converted in place. Idempotent: skips rows whose
description already looks like HTML (starts with `<` or contains an
HTML tag) unless --force is passed.

Usage:
    python manage.py convert_descriptions_to_html
    python manage.py convert_descriptions_to_html --slugs pinocchio,hamlet
    python manage.py convert_descriptions_to_html --force --dry-run
"""
from __future__ import annotations

import logging
import re

from django.core.management.base import BaseCommand

logger = logging.getLogger('morpheus.catalog')


_HTML_TAG_RE = re.compile(r'<\w+[\s>]')
_MARKDOWN_TELL = re.compile(r'(?m)^(#{1,3} |\[[^\]]+\]\(|\*\*[^*]+\*\*)')


def _looks_like_html(value: str) -> bool:
    if not value:
        return False
    v = value.lstrip()
    if v.startswith('<') and _HTML_TAG_RE.search(v[:40]) is not None:
        return True
    # A description that opens with prose then has tags inline is still
    # HTML for our purposes.
    return bool(_HTML_TAG_RE.search(value))


def _looks_like_markdown(value: str) -> bool:
    return bool(_MARKDOWN_TELL.search(value or ''))


class Command(BaseCommand):
    help = 'Convert Product.description from markdown to HTML (TipTap-ready).'

    def add_arguments(self, parser) -> None:
        parser.add_argument('--slugs', default='', help='Comma-separated slugs (default: all active).')
        parser.add_argument('--force', action='store_true',
                            help='Convert even rows that already look like HTML.')
        parser.add_argument('--dry-run', action='store_true', help='Show what would change; do not write.')

    def handle(self, *args, **opts) -> None:
        from plugins.installed.catalog.models import Product
        from core.templatetags.morph import markdown_to_html

        slugs = [s.strip() for s in (opts.get('slugs') or '').split(',') if s.strip()]
        force = bool(opts['force'])
        dry = bool(opts['dry_run'])

        qs = Product.objects.filter(status='active').order_by('name')
        if slugs:
            qs = qs.filter(slug__in=slugs)

        converted = skipped = empty = 0
        for product in qs:
            body = product.description or ''
            if not body.strip():
                empty += 1
                continue
            if _looks_like_html(body) and not force:
                skipped += 1
                continue
            if not _looks_like_markdown(body) and not force:
                # Plain prose with no markdown markers — wrap in <p>.
                pass

            html = markdown_to_html(body)
            if html == body:
                skipped += 1
                continue

            self.stdout.write(f'→ {product.slug}: {len(body)} chars md → {len(html)} chars html')
            if dry:
                continue

            product.description = html
            product.save(update_fields=['description'])
            converted += 1

        self.stdout.write(self.style.SUCCESS(
            f'done — converted={converted} skipped={skipped} empty={empty}'
        ))
