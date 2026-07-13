"""
apply_external_links — append a "Sources & references" section of VERIFIED
external links to each book's long description.

Two kinds of links, both hallucination-free:

  1. **Data-derived** (deterministic, always valid) — built only from
     identifiers we already store and reconcile:
       • Open Library work id (metafield ``book.openlibrary``) → openlibrary.org/works/<id>
       • OCLC number       (metafield ``book.oclc``)         → search.worldcat.org/title/<n>
       • ISBN-13           (metafield ``identifiers.isbn13``) → openlibrary.org/isbn/<isbn>
     A book with none of these gets no external links (correct — we never invent one).

  2. **Verified web** (opt-in, --verify-web, default on) — the book's author linked
     to their Wikipedia article, but ONLY after the Wikipedia REST summary API
     confirms a real "standard" article exists (not missing, not a disambiguation).
     We never write an unverified/guessed URL.

Links are real ``<a href … rel="noopener" target="_blank">`` — authoritative
references, so followable — and survive ``Product.save()`` sanitisation
(core.utils.html allows a[href,title,target,rel]).

Idempotent via the ``seo.external_links_applied`` metafield (mirrors
apply_internal_links). Re-applies if a later populate_descriptions regenerate
wiped the block.

Usage:
    python manage.py apply_external_links
    python manage.py apply_external_links --slugs dune,frankenstein --dry-run
    python manage.py apply_external_links --no-verify-web        # data-derived only
    python manage.py apply_external_links --force
"""

from __future__ import annotations

import html as _html
import logging
import re

from django.core.management.base import BaseCommand

logger = logging.getLogger('morpheus.seo.external_links')

NAMESPACE = 'seo'
KEY = 'external_links_applied'
# No '&' in the heading on purpose: Product.save() runs sanitize_richtext, which
# escapes a bare '&' to '&amp;'. A heading with '&' would then never match our
# idempotency / strip regexes against the stored HTML, re-appending forever.
HEADING = 'Sources and references'
# populate_descriptions preserves a trailing block by this heading across
# regenerates (see _extract_related_reading) — keep the two in sync.


def _read_identifiers(product) -> dict[str, str]:
    """ISBN-13 / OCLC / Open Library work id from the shared metafield store.

    Read directly (not via book_product) so the seo plugin stays decoupled.
    """
    from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

    out = {'isbn13': '', 'oclc': '', 'openlibrary': ''}
    try:
        ident = Metafield.objects.for_obj(product, ns='identifiers') or {}
        out['isbn13'] = str(ident.get('identifiers.isbn13') or ident.get('isbn13') or '').strip()
        book_ns = Metafield.objects.for_obj(product, ns='book') or {}
        out['oclc'] = str(book_ns.get('book.oclc') or book_ns.get('oclc') or '').strip()
        out['openlibrary'] = str(
            book_ns.get('book.openlibrary') or book_ns.get('openlibrary') or ''
        ).strip()
    except Exception:  # noqa: BLE001, S110 — metafields optional
        pass
    return out


def _read_author(product) -> str:
    """Author name — prefer the BookProduct model column, fall back to the
    legacy ``book.author`` metafield. Never raises."""
    author = ''
    book = getattr(product, 'book', None)
    if book is not None:
        author = (getattr(book, 'author', '') or '').strip()
    if not author:
        try:
            from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

            book_ns = Metafield.objects.for_obj(product, ns='book') or {}
            author = str(book_ns.get('book.author') or '').strip()
        except Exception:  # noqa: BLE001, S110
            pass
    return author


def _verify_wikipedia(author: str) -> str:
    """Return the canonical Wikipedia URL for ``author`` iff a real article
    exists, else ''. Uses the REST summary API; accepts only type='standard'
    (rejects missing pages and disambiguation)."""
    import requests  # noqa: PLC0415

    title = author.strip().replace(' ', '_')
    if not title:
        return ''
    try:
        from urllib.parse import quote  # noqa: PLC0415

        resp = requests.get(
            f'https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}',
            headers={'User-Agent': 'MorpheusBookshop/1.0 (dotbooks.store; SEO references)'},
            timeout=8,
        )
        if resp.status_code != 200:
            return ''
        data = resp.json()
        if data.get('type') != 'standard':  # skip disambiguation / missing
            return ''
        url = (data.get('content_urls', {}).get('desktop', {}) or {}).get('page', '')
        return url or f'https://en.wikipedia.org/wiki/{title}'
    except Exception as exc:  # noqa: BLE001
        logger.info('wikipedia verify failed for %r: %s', author, exc)
        return ''


def _ext(href: str, label: str) -> str:
    return (
        f'<a href="{_html.escape(href, quote=True)}" '
        f'rel="noopener" target="_blank">{_html.escape(label)}</a>'
    )


def _build_links(product, *, verify_web: bool) -> list[str]:
    """Ordered list of verified external <a> links for this book."""
    ids = _read_identifiers(product)
    links: list[str] = []
    if ids['openlibrary']:
        olid = ids['openlibrary']
        links.append(_ext(f'https://openlibrary.org/works/{olid}', 'Open Library'))
    if ids['oclc']:
        oclc = re.sub(r'\D', '', ids['oclc'])
        if oclc:
            links.append(_ext(f'https://search.worldcat.org/title/{oclc}', 'WorldCat'))
    if ids['isbn13']:
        isbn = re.sub(r'[^0-9Xx]', '', ids['isbn13'])
        if isbn:
            links.append(_ext(f'https://openlibrary.org/isbn/{isbn}', 'Editions & formats'))
    if verify_web:
        author = _read_author(product)
        if author:
            wiki = _verify_wikipedia(author)
            if wiki:
                links.append(_ext(wiki, f'{author} on Wikipedia'))
    return links


def _block(links: list[str]) -> str:
    joined = ', '.join(links)
    return f'\n<h2>{HEADING}</h2>\n<p>Verified references for this edition: {joined}.</p>'


def _strip_previous(body: str) -> str:
    m = re.search(rf'<h2[^>]*>\s*{re.escape(HEADING)}\s*</h2>', body, flags=re.I)
    if m:
        return body[: m.start()].rstrip()
    return body


class Command(BaseCommand):
    help = 'Append a verified external-links "Sources & references" block to book descriptions.'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--slugs', default='', help='Comma-separated slugs (default: all active).'
        )
        parser.add_argument(
            '--no-verify-web',
            action='store_true',
            help='Skip the Wikipedia author lookup; data-derived links only.',
        )
        parser.add_argument('--force', action='store_true', help='Rebuild the block + re-mark.')
        parser.add_argument('--dry-run', action='store_true', help='Show changes; do not write.')
        parser.add_argument('--limit', type=int, default=0, help='Stop after N writes (0 = all).')

    def handle(self, *args, **opts) -> None:  # noqa: PLR0915
        from django.contrib.contenttypes.models import ContentType

        from plugins.installed.catalog.models import Product
        from plugins.installed.metafields.models import Metafield

        slugs = [s.strip() for s in (opts.get('slugs') or '').split(',') if s.strip()]
        verify_web = not bool(opts['no_verify_web'])
        force = bool(opts['force'])
        dry = bool(opts['dry_run'])
        limit = int(opts['limit'])

        qs = Product.objects.filter(status='active').order_by('name')
        if slugs:
            qs = qs.filter(slug__in=slugs)

        ct = ContentType.objects.get_for_model(Product)
        applied = skipped = nolinks = 0

        for product in qs:
            body = product.description or ''
            flag = Metafield.objects.filter(
                content_type=ct, object_id=str(product.pk), namespace=NAMESPACE, key=KEY
            ).first()
            # Skip if marked done AND the block is still present (a regenerate
            # that wiped it should re-apply, like apply_internal_links).
            if flag and not force and f'<h2>{HEADING}</h2>' in body:
                skipped += 1
                continue

            links = _build_links(product, verify_web=verify_web)
            if not links:
                nolinks += 1
                continue

            new_body = _strip_previous(body).rstrip() + '\n' + _block(links) + '\n'
            self.stdout.write(f'→ {product.slug}: {len(links)} external link(s)')
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
                    'value': str(len(links)),
                    'value_type': 'string',
                    'description': 'Count of verified external links appended by apply_external_links.',
                },
            )
            applied += 1
            if limit and applied >= limit:
                self.stdout.write(self.style.WARNING(f'stopped at --limit {limit}'))
                break

        self.stdout.write(
            self.style.SUCCESS(f'done — applied={applied} skipped={skipped} no_links={nolinks}')
        )
