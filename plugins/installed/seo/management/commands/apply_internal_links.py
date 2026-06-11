"""
apply_internal_links — append a "Related reading" section with 3
internal markdown links to every long product description that
doesn't yet have any internal `<a href>` references.

Idempotent: skips products whose ``seo.internal_links_applied``
metafield is set, unless --force is passed. Tracks per-product so
re-running picks up new products added after the last run without
re-touching the old ones.

Why this exists: the SEO audit rule penalises descriptions with zero
internal links, and AI search engines (Perplexity, ChatGPT, AI
Overviews) overweight pages with strong internal-link graphs. Linking
related books from each long description is the highest-leverage AEO
move for an indie bookshop.

Usage:
    python manage.py apply_internal_links
    python manage.py apply_internal_links --slugs pinocchio,dorian-gray
    python manage.py apply_internal_links --force --dry-run
"""

from __future__ import annotations

import logging
import re

from django.core.management.base import BaseCommand

logger = logging.getLogger('morpheus.seo.internal_links')

NAMESPACE = 'seo'
KEY = 'internal_links_applied'
SECTION_MARKER = '## Related reading'


def _has_internal_link(html: str) -> bool:
    return bool(re.search(r'<a\s+[^>]*href=', html or '', flags=re.I))


def _has_markdown_link(text: str) -> bool:
    return bool(re.search(r'\[[^\]]+\]\(/products/[^)]+\)', text or ''))


def _build_block(suggestions: list[dict], *, as_html: bool) -> str:
    """Compose the 'Related reading' block. Emits HTML when the
    surrounding description is HTML (TipTap-stored), otherwise
    Markdown (legacy)."""
    if not suggestions:
        return ''

    def link(s):
        return (
            f'<a href="/products/{s["slug"]}/">{s["name"]}</a>'
            if as_html
            else f'[{s["name"]}](/products/{s["slug"]}/)'
        )

    if len(suggestions) == 1:
        sentence = f'If this resonates, you might also reach for {link(suggestions[0])}.'
    elif len(suggestions) == 2:
        sentence = (
            f'If this resonates, you might also reach for '
            f'{link(suggestions[0])} or {link(suggestions[1])}.'
        )
    else:
        sentence = (
            f'If this resonates, you might also reach for '
            f'{link(suggestions[0])}, {link(suggestions[1])}, '
            f'or {link(suggestions[2])}.'
        )

    if as_html:
        return f'\n<h2>Related reading</h2>\n<p>{sentence}</p>'
    return '\n'.join(['', SECTION_MARKER, '', sentence])


class Command(BaseCommand):
    help = 'Append related-reading internal links to product long descriptions.'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--slugs', default='', help='Comma-separated product slugs (default: all active).'
        )
        parser.add_argument(
            '--limit-per-product',
            type=int,
            default=3,
            help='How many internal links to insert per product (default 3).',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite existing Related-reading section + re-mark.',
        )
        parser.add_argument(
            '--dry-run', action='store_true', help='Show what would change; do not write.'
        )

    def handle(self, *args, **opts) -> None:  # noqa: PLR0915
        from django.contrib.contenttypes.models import ContentType

        from plugins.installed.catalog.models import Product
        from plugins.installed.metafields.models import Metafield
        from plugins.installed.seo.services import suggest_internal_links_for

        slugs = [s.strip() for s in (opts.get('slugs') or '').split(',') if s.strip()]
        limit = max(1, int(opts['limit_per_product']))
        force = bool(opts['force'])
        dry = bool(opts['dry_run'])

        qs = Product.objects.filter(status='active').order_by('name')
        if slugs:
            qs = qs.filter(slug__in=slugs)

        ct = ContentType.objects.get_for_model(Product)
        applied = skipped = nolinks = 0

        for product in qs:
            existing_flag = Metafield.objects.filter(
                content_type=ct,
                object_id=str(product.pk),
                namespace=NAMESPACE,
                key=KEY,
            ).first()
            body = product.description or ''
            if existing_flag and not force:
                # If the metafield records specific slugs but NONE of
                # them are present in the current description, the
                # description was overwritten by a later regenerate
                # (populate_descriptions) and the link block was lost.
                # Re-apply so the audit's "no internal links" rule
                # actually clears.
                recorded = (existing_flag.value or '').strip()
                recorded_slugs = [s for s in recorded.split(',') if s and s != 'already-linked']
                if recorded_slugs and not any(f'/products/{s}/' in body for s in recorded_slugs):
                    logger.info(
                        'apply_internal_links: %s recorded as applied (%s) but '
                        'description shows no link traces — re-applying',
                        product.slug,
                        recorded,
                    )
                else:
                    skipped += 1
                    continue

            if _has_internal_link(body) or _has_markdown_link(body):
                # Already has links — record that we considered it so
                # the next run doesn't re-evaluate.
                if not dry:
                    Metafield.objects.update_or_create(
                        content_type=ct,
                        object_id=str(product.pk),
                        namespace=NAMESPACE,
                        key=KEY,
                        defaults={'value': 'already-linked', 'value_type': 'string'},
                    )
                skipped += 1
                continue

            suggestions = suggest_internal_links_for(product, limit=limit)
            if not suggestions:
                nolinks += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'  {product.slug}: no suggestions available (no embeddings + no category siblings)'
                    )
                )
                continue

            # Detect whether the surrounding description is HTML
            # (TipTap-stored, post-conversion) or legacy Markdown so
            # the appended block matches.
            as_html = body.lstrip().startswith('<') or bool(re.search(r'<\w+[\s>]', body[:80]))

            # Strip a previous Related-reading section before re-appending
            # — only relevant when --force.
            stripped = body
            if SECTION_MARKER in stripped:
                idx = stripped.find(SECTION_MARKER)
                stripped = stripped[:idx].rstrip()
            elif as_html:
                # HTML form — look for `<h2>Related reading</h2>` onwards.
                m = re.search(r'<h2[^>]*>\s*Related reading\s*</h2>', stripped, flags=re.I)
                if m:
                    stripped = stripped[: m.start()].rstrip()

            block = _build_block(suggestions, as_html=as_html)
            new_body = stripped.rstrip() + '\n' + block + '\n'

            self.stdout.write(
                f'→ {product.slug}: appending {len(suggestions)} link(s) '
                f'({", ".join(s["slug"] for s in suggestions)})'
            )

            if dry:
                continue

            product.description = new_body
            product.save(update_fields=['description'])
            Metafield.objects.update_or_create(
                content_type=ct,
                object_id=str(product.pk),
                namespace=NAMESPACE,
                key=KEY,
                defaults={
                    'value': ','.join(s['slug'] for s in suggestions),
                    'value_type': 'string',
                    'description': 'Slugs of internal links appended by apply_internal_links.',
                },
            )
            applied += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'done — applied={applied} skipped={skipped} no_suggestions={nolinks}'
            )
        )
