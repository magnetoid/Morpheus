"""Backfill Book reconciliation identifiers from Open Library.

These are public-domain works: each has dozens–hundreds of editions' ISBNs,
none of them ours, so fabricating an ISBN would mis-associate the edition.
Instead we store the stable Open Library *work* id (→ sameAs) and an OCLC
number (→ edition identifier) — both accepted by Google's Book structured
data, both strictly correct. Conservative matching: the author surname must
appear in the candidate's authors AND the title must closely match, else the
book is skipped (a wrong id is worse than none).

    python manage.py backfill_book_identifiers --dry-run --limit 20
    python manage.py backfill_book_identifiers            # writes
    python manage.py backfill_book_identifiers --overwrite # re-resolve all
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from django.core.management.base import BaseCommand

OL_SEARCH = 'https://openlibrary.org/search.json'
_FIELDS = 'title,author_name,oclc,key,edition_count'


def _norm(s: str) -> str:
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in (s or '').lower()).split())


def _surname(author: str) -> str:
    parts = _norm(author).split()
    return parts[-1] if parts else ''


def pick_work(title: str, author: str, docs: list[dict]) -> tuple[str | None, str | None]:
    """Best conservative match → (olid, oclc). Author surname must match and the
    title must be equal or a containment match (handles subtitles). Among
    matches, prefer the most-published work (highest edition_count)."""
    nt = _norm(title)
    surname = _surname(author)
    best: tuple[str, str, int] | None = None
    for d in docs:
        dtitle = _norm(d.get('title') or '')
        authors = [_norm(a) for a in (d.get('author_name') or [])]
        if surname and not any(surname in a for a in authors):
            continue
        if not (dtitle == nt or (nt and (nt in dtitle or dtitle in nt))):
            continue
        key = d.get('key') or ''
        olid = key.rsplit('/', 1)[-1]
        if not olid.startswith('OL'):
            continue
        oclc_list = d.get('oclc') or []
        oclc = str(oclc_list[0]) if oclc_list else ''
        ed = int(d.get('edition_count') or 0)
        if best is None or ed > best[2]:
            best = (olid, oclc, ed)
    if best:
        return best[0], (best[1] or None)
    return None, None


def _lookup(title: str, author: str, timeout: int = 15) -> list[dict]:
    qs = urllib.parse.urlencode({'title': title, 'author': author, 'fields': _FIELDS, 'limit': 5})
    req = urllib.request.Request(  # noqa: S310 — fixed https host (openlibrary.org)
        f'{OL_SEARCH}?{qs}', headers={'User-Agent': 'Morpheus/1.0'}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310  # nosec B310 — fixed https host
        return (json.loads(resp.read().decode('utf-8')) or {}).get('docs', []) or []


class Command(BaseCommand):
    help = 'Backfill Open Library work id (sameAs) + OCLC for book products.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Resolve but do not write.')
        parser.add_argument('--limit', type=int, default=0, help='Max books to process (0 = all).')
        parser.add_argument('--sleep', type=float, default=1.0, help='Seconds between API calls.')
        parser.add_argument(
            '--overwrite', action='store_true', help='Re-resolve books that already have an id.'
        )

    def handle(self, *args, **opts):
        from plugins.installed.book_product.models import BookProduct
        from plugins.installed.metafields.models import Metafield

        dry, limit, sleep, overwrite = (
            opts['dry_run'],
            opts['limit'],
            opts['sleep'],
            opts['overwrite'],
        )
        qs = (
            BookProduct.objects.exclude(author='')
            .select_related('product')
            .filter(product__status='active')
            .order_by('product__slug')
        )
        matched = skipped = nomatch = errors = 0
        processed = 0
        for book in qs.iterator():
            product = book.product
            if not overwrite:
                existing = Metafield.objects.for_obj(product, ns='book') or {}
                if existing.get('book.openlibrary') or existing.get('openlibrary'):
                    skipped += 1
                    continue
            if limit and processed >= limit:
                break
            processed += 1
            title, author = product.name, book.author
            try:
                docs = _lookup(title, author)
                olid, oclc = pick_work(title, author, docs)
            except Exception as e:  # noqa: BLE001 — network/parse; keep going
                errors += 1
                self.stderr.write(f'  ! {product.slug}: {e}')
                time.sleep(sleep)
                continue
            if not olid:
                nomatch += 1
                self.stdout.write(f'  – no match: {title} / {author}')
                time.sleep(sleep)
                continue
            matched += 1
            tag = 'DRY' if dry else 'SET'
            self.stdout.write(f'  ✓ [{tag}] {product.slug} → OL={olid} OCLC={oclc or "—"}')
            if not dry:
                Metafield.objects.set(product, namespace='book', key='openlibrary', value=olid)
                if oclc:
                    Metafield.objects.set(product, namespace='book', key='oclc', value=oclc)
            time.sleep(sleep)

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone. matched={matched} no-match={nomatch} '
                f'skipped(existing)={skipped} errors={errors} '
                f'{"(dry-run, nothing written)" if dry else ""}'
            )
        )
