"""Populate the long `Product.description` field for every active product.

Uses the active AI provider (set in /dashboard/settings/ai/) to write
a ~200-word editorial blurb per book — title, author, and short
description go in, a warm spoiler-free piece comes out.

Idempotent by default — skips any product whose description is
already longer than --min-length characters. Pass --force to overwrite.

Usage:
    python manage.py populate_descriptions
    python manage.py populate_descriptions --min-length 400 --force
    python manage.py populate_descriptions --slugs pride-and-prejudice,moby-dick
    python manage.py populate_descriptions --dry-run
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger('morpheus.catalog')


_PROMPT_TEMPLATE = (
    "Write a 180-220 word editorial blurb for the book \"{title}\" by {author}. "
    "Tone: warm, literary, smart — like the back-cover copy from a good "
    "independent bookshop. NO spoilers. Mention themes, the era, and why "
    "the book still matters. Avoid generic phrases like \"timeless classic\" "
    "and \"masterpiece\". Open with a vivid sentence that grabs the reader. "
    "Plain text only — no markdown, no headings, no bullet points. "
    "End with a single short paragraph naming who it's for or what mood "
    "it fits.\n\n"
    "Context (short blurb already on file): {short}\n\n"
    "Output the blurb only — no preamble, no quotes around it."
)


def _book_meta(product) -> tuple[str, str, str]:
    """Return (title, author, short_description) from product + metafields."""
    title = (product.name or '').strip() or 'Untitled'
    short = (getattr(product, 'short_description', '') or '').strip()
    author = ''
    try:
        from django.contrib.contenttypes.models import ContentType
        from plugins.installed.metafields.models import Metafield
        ct = ContentType.objects.get_for_model(type(product))
        m = Metafield.objects.filter(
            content_type=ct, object_id=product.pk,
            namespace='book', key='author',
        ).first()
        if m and m.value:
            author = str(m.value)
    except Exception:  # noqa: BLE001
        pass
    return title, author or 'an anonymous author', short


class Command(BaseCommand):
    help = 'Generate long-form Product.description via the active AI provider.'

    def add_arguments(self, parser) -> None:
        parser.add_argument('--slugs', default='', help='Comma-separated product slugs (default: all active).')
        parser.add_argument('--min-length', type=int, default=400,
                            help='Skip products whose description is already this many chars or more. Default 400.')
        parser.add_argument('--force', action='store_true', help='Overwrite even if min-length is met.')
        parser.add_argument('--dry-run', action='store_true', help='Show what would change; do not write.')
        parser.add_argument('--limit', type=int, default=0, help='Stop after this many writes (0 = no limit).')

    def handle(self, *args, **opts) -> None:
        from plugins.installed.catalog.models import Product

        slugs = [s.strip() for s in (opts.get('slugs') or '').split(',') if s.strip()]
        min_len = int(opts['min_length'])
        force = bool(opts['force'])
        dry = bool(opts['dry_run'])
        limit = int(opts['limit'])

        qs = Product.objects.filter(status='active')
        if slugs:
            qs = qs.filter(slug__in=slugs)

        # Resolve the LLM provider via the same registry Linda uses.
        try:
            from plugins.installed.ai_assistant.services.llm import get_llm
            llm = get_llm()
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(self.style.ERROR(
                f'No AI provider available: {exc}. Configure one in '
                f'/dashboard/settings/ai/ and retry.'
            ))
            return

        written = skipped = errored = 0
        for product in qs:
            existing_len = len(product.description or '')
            if not force and existing_len >= min_len:
                skipped += 1
                continue

            title, author, short = _book_meta(product)
            prompt = _PROMPT_TEMPLATE.format(title=title, author=author, short=short or '(none)')
            self.stdout.write(f'→ {product.slug} ({existing_len} chars → generating…)')
            if dry:
                continue

            try:
                new_desc = (llm.complete(prompt, temperature=0.6, max_tokens=400) or '').strip()
            except Exception as exc:  # noqa: BLE001
                logger.warning('llm error for %s: %s', product.slug, exc)
                errored += 1
                continue
            if len(new_desc) < 150:
                logger.warning('blurb too short for %s (%d chars) — skipping', product.slug, len(new_desc))
                errored += 1
                continue

            product.description = new_desc
            product.save(update_fields=['description'])
            written += 1
            if limit and written >= limit:
                self.stdout.write(self.style.WARNING(f'stopped at --limit {limit}'))
                break

        self.stdout.write(self.style.SUCCESS(
            f'done — written={written} skipped={skipped} errored={errored}'
        ))
