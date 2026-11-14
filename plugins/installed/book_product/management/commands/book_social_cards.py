"""Draw books' social cards (social_cards.py) from the command line.

One book, the canary (draws and stores it whether or not the feature is on, so
the card can be checked before anyone sees it):

    python manage.py book_social_cards --product partners-in-crime

Only a local file, nothing stored:

    python manage.py book_social_cards --product partners-in-crime --preview /tmp/card.jpg

A bounded backfill: the active books whose card is missing or out of date,
in a stable order, at most --limit per run. A book that is current is skipped,
so running it again carries on where the last run stopped:

    python manage.py book_social_cards --all --limit 50 [--dry-run]
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

MAX_LIMIT = 500


class Command(BaseCommand):
    help = "Draw books' social cards: one book (--product), or a bounded backfill (--all)."

    def add_arguments(self, parser):
        parser.add_argument('--product', action='append', default=[], help='Product slug or id.')
        parser.add_argument('--all', action='store_true', help='Books whose card is missing.')
        parser.add_argument('--limit', type=int, default=25, help=f'Cards per run (≤ {MAX_LIMIT}).')
        parser.add_argument('--dry-run', action='store_true', help='List, draw nothing.')
        parser.add_argument('--preview', default='', help='Write the JPEG here; store nothing.')

    def handle(self, *args, **opts):
        from plugins.installed.book_product import social_cards

        if bool(opts['product']) == bool(opts['all']):
            raise CommandError('Pass --product <slug> (repeatable) or --all.')
        if opts['preview'] and len(opts['product']) != 1:
            raise CommandError('--preview takes exactly one --product.')
        if not social_cards.enabled():
            self.stdout.write(
                'Note: social cards are off for this store; cards are stored, not shown.'
            )
        books = self._books(opts) if opts['product'] else self._stale_books(opts)
        for book in books:
            self._one(book, opts)

    def _books(self, opts):
        from django.db.models import Q

        from plugins.installed.book_product.models import BookProduct

        for ref in opts['product']:
            q = Q(product__slug=ref)
            if len(ref) == 36:
                q |= Q(product__pk=ref)
            book = BookProduct.objects.select_related('product').filter(q).first()
            if book is None:
                raise CommandError(f'No book for {ref!r}.')
            yield book

    def _stale_books(self, opts):
        from plugins.installed.book_product import social_cards
        from plugins.installed.book_product.models import BookProduct

        limit = max(1, min(opts['limit'], MAX_LIMIT))
        found = 0
        qs = (
            BookProduct.objects.filter(product__status='active')
            .select_related('product')
            .prefetch_related('product__images')
            .order_by('pk')
        )
        for book in qs.iterator(chunk_size=200):
            inputs = social_cards.card_inputs(book)
            if inputs is None or book.social_card_key == inputs.fingerprint():
                continue
            yield book
            found += 1
            if found >= limit:
                self.stdout.write(f'Stopped at --limit {limit}; run again to continue.')
                return

    def _one(self, book, opts):
        from django.core.files.storage import default_storage

        from morpheus.core import absolutize
        from plugins.installed.book_product import social_cards
        from plugins.installed.book_product.social_card_render import CardError

        slug = book.product.slug
        if opts['dry_run']:
            self.stdout.write(f'would draw {slug}')
            return
        if opts['preview']:
            inputs = social_cards.card_inputs(book)
            if inputs is None:
                raise CommandError(f'{slug} has no cover or no name.')
            try:
                data = social_cards.draw(inputs)
            except CardError as e:
                raise CommandError(f'{slug}: {e}') from e
            with open(opts['preview'], 'wb') as fh:
                fh.write(data)
            self.stdout.write(f'{slug}: wrote {opts["preview"]} ({len(data)} bytes)')
            return
        outcome = social_cards.render_and_store(book.pk)
        book.refresh_from_db(fields=['social_card'])
        url = absolutize(default_storage.url(book.social_card.name)) if book.social_card else ''
        self.stdout.write(f'{slug}: {outcome} {url}'.rstrip())
