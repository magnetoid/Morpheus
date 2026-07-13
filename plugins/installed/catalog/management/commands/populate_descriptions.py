"""Populate Product.short_description and Product.description via the active LLM.

Single LLM call per product returns strict JSON `{short, long}`. The
short is a 30–50 word hook; the long is 600–800 words of Markdown
structured into five H2 sections — drives both human readability and
the SEO audit's H2/H3 / word-count rules.

Idempotent by default — skips any product whose long description is
already longer than `--min-length` chars. Pass `--force` to overwrite.

Usage:
    python manage.py populate_descriptions
    python manage.py populate_descriptions --min-length 800 --force
    python manage.py populate_descriptions --slugs pride-and-prejudice,moby-dick
    python manage.py populate_descriptions --dry-run
    python manage.py populate_descriptions --no-short    # long only
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from core.llm_parsing import parse_llm_json

logger = logging.getLogger('morpheus.catalog')


_SYSTEM_PROMPT = (
    'You write book copy for an independent online bookshop. Tone: '
    'warm, literary, smart — like the back-cover blurb a thoughtful '
    'bookseller would hand-write. No spoilers. Avoid clichés ("timeless '
    'classic", "masterpiece", "instant classic"). No marketing fluff. '
    'Always return STRICT JSON only — no preamble, no markdown fences, '
    'no commentary around it.'
)


_PROMPT_TEMPLATE = (
    'Write a rich pair of descriptions for "{title}" by {author}.\n\n'
    'Context (short blurb already on file): {short}\n\n'
    'Return STRICT JSON only, exactly:\n'
    '{{"short": "...", "long": "..."}}\n\n'
    '"short" — 30–50 words, one or two vivid sentences that grab the '
    'reader. No spoilers. Plain text (no markdown).\n\n'
    '"long" — 600–800 words of Markdown, structured exactly as:\n'
    '  <50-word vivid opener paragraph (no heading)>\n'
    "  ## What it's about\n"
    '  <120–150 words: plot or contents tour, spoiler-free>\n'
    '  ## Themes\n'
    '  <120–150 words: 2–3 main themes the book explores>\n'
    '  ## Why it still matters\n'
    '  <120–150 words: current relevance / lasting influence>\n'
    "  ## Who it's for\n"
    '  <80–100 words: reader profile — mood, taste, adjacent reads>\n'
    '  ## On reading it now\n'
    "  <80–100 words: a short reflection from a 2026 reader's vantage>\n"
    'Plain prose per section, no bullet lists, no nested headings.'
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
            content_type=ct,
            object_id=product.pk,
            namespace='book',
            key='author',
        ).first()
        if m and m.value:
            author = str(m.value)
    except Exception:  # noqa: BLE001, S110
        pass
    return title, author or 'an anonymous author', short


def _extract_related_reading(body: str) -> str:
    """Return the trailing link block(s) from ``body``, or '' if none.

    Preserves BOTH the 'Related reading' section (internal links, written by
    apply_internal_links) and the 'Sources & references' section (verified
    external links, written by apply_external_links) across a description
    regeneration — returning from the EARLIEST heading to the end keeps every
    appended block. Otherwise a --force regenerate silently drops the link work.
    """
    if not body:
        return ''
    import re as _re

    starts = []
    # HTML form (TipTap-stored) — either heading.
    for heading in ('Related reading', 'Sources and references'):
        m = _re.search(rf'<h2[^>]*>\s*{_re.escape(heading)}\s*</h2>', body, flags=_re.I)
        if m:
            starts.append(m.start())
    # Markdown form (legacy / LLM Markdown).
    for marker in ('## Related reading', '## Sources and references'):
        idx = body.find(marker)
        if idx >= 0:
            starts.append(idx)
    if starts:
        return body[min(starts) :].rstrip() + '\n'
    return ''


class Command(BaseCommand):
    help = (
        'Generate rich Product.short_description + Product.description via the active AI provider.'
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--slugs', default='', help='Comma-separated product slugs (default: all active).'
        )
        parser.add_argument(
            '--min-length',
            type=int,
            default=800,
            help='Skip products whose long description is already this many chars or more. Default 800.',
        )
        parser.add_argument(
            '--force', action='store_true', help='Overwrite even if min-length is met.'
        )
        parser.add_argument(
            '--dry-run', action='store_true', help='Show what would change; do not write.'
        )
        parser.add_argument(
            '--limit', type=int, default=0, help='Stop after this many writes (0 = no limit).'
        )
        parser.add_argument(
            '--no-short', action='store_true', help='Skip writing short_description (long only).'
        )

    def handle(self, *args, **opts) -> None:  # noqa: PLR0915
        from plugins.installed.catalog.models import Product

        slugs = [s.strip() for s in (opts.get('slugs') or '').split(',') if s.strip()]
        min_len = int(opts['min_length'])
        force = bool(opts['force'])
        dry = bool(opts['dry_run'])
        limit = int(opts['limit'])
        skip_short = bool(opts['no_short'])

        qs = Product.objects.filter(status='active')
        if slugs:
            qs = qs.filter(slug__in=slugs)

        try:
            from plugins.installed.ai_assistant.services.llm import get_llm

            llm = get_llm()
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(
                self.style.ERROR(
                    f'No AI provider available: {exc}. Configure one in '
                    f'/dashboard/settings/ai/ and retry.'
                )
            )
            return

        written = skipped = errored = 0
        for product in qs:
            existing_len = len(product.description or '')
            if not force and existing_len >= min_len:
                skipped += 1
                continue

            title, author, short = _book_meta(product)
            prompt = _PROMPT_TEMPLATE.format(
                title=title,
                author=author,
                short=short or '(none)',
            )
            self.stdout.write(f'→ {product.slug} ({existing_len} chars → generating…)')
            if dry:
                continue

            try:
                raw = llm.complete(
                    prompt,
                    system=_SYSTEM_PROMPT,
                    temperature=0.6,
                    max_tokens=1800,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning('llm error for %s: %s', product.slug, exc)
                errored += 1
                continue

            data = parse_llm_json(raw or '') or {}
            if not isinstance(data, dict):
                data = {}
            long_desc = (data.get('long') or '').strip()
            short_desc = (data.get('short') or '').strip()

            if len(long_desc) < 1500:
                logger.warning(
                    'long description too short for %s (%d chars) — skipping',
                    product.slug,
                    len(long_desc),
                )
                errored += 1
                continue

            # Preserve any existing Related-reading section so that
            # internal links (written by apply_internal_links) survive
            # a description regeneration. Otherwise every populate run
            # silently undoes the link work, the metafield falsely
            # claims "applied", and the SEO audit penalises the page.
            existing_related = _extract_related_reading(product.description or '')

            update_fields = ['description']
            product.description = (
                f'{long_desc}\n{existing_related}' if existing_related else long_desc
            )
            if not skip_short and len(short_desc) >= 25:
                product.short_description = short_desc[:500]
                update_fields.append('short_description')

            product.save(update_fields=update_fields)
            written += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f'  saved {product.slug}: short={len(short_desc)} long={len(long_desc)}'
                )
            )
            if limit and written >= limit:
                self.stdout.write(self.style.WARNING(f'stopped at --limit {limit}'))
                break

        self.stdout.write(
            self.style.SUCCESS(f'done — written={written} skipped={skipped} errored={errored}')
        )
