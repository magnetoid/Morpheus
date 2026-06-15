"""AI-classify books into Genres + Topics from title/author/synopsis.

Batches books to the active LLM (grok/anthropic/…), asks for 1–3 genres from a
controlled vocabulary (so genres stay clean) + 2–4 free-form topic tags, then
get_or_creates the Genre/Topic rows and tags each book. Enriches by default
(adds, never removes); ``--replace`` clears a book's genres/topics first.

    # preview 10 books, write nothing
    python manage.py classify_books --limit 10
    # tag every book missing topics, for real
    python manage.py classify_books --only-missing-topics --apply

Idempotent (get_or_create by slug), fail-soft per batch, resumable via
``--only-missing-topics``.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils.text import slugify

# Controlled genre vocabulary — the LLM picks from these so genres don't sprawl.
GENRE_VOCAB = [
    'Fiction',
    'Literary Fiction',
    'Science Fiction',
    'Fantasy',
    'Mystery',
    'Thriller',
    'Crime',
    'Horror',
    'Romance',
    'Historical Fiction',
    'Adventure',
    'Poetry',
    'Drama',
    'Short Stories',
    'Non-fiction',
    'Biography & Memoir',
    'History',
    'Philosophy',
    'Science',
    'Psychology',
    'Self-help',
    'Politics',
    'Religion & Spirituality',
    'Art & Design',
    'Travel',
    'Essays',
    "Children's",
    'Young Adult',
    'Classics',
    'Humor',
    'Nature & Environment',
    'Business',
]

_SYSTEM = (
    'You are a meticulous librarian. You classify books and output STRICT JSON '
    'only — no prose, no markdown fences.'
)


class Command(BaseCommand):
    help = 'AI-classify books into Genres + Topics from title/author/synopsis.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true', help='Write changes (default: dry-run).'
        )
        parser.add_argument('--limit', type=int, default=0, help='Max books to process (0 = all).')
        parser.add_argument('--batch-size', type=int, default=8, help='Books per LLM call.')
        parser.add_argument(
            '--only-missing-topics',
            action='store_true',
            help='Skip books that already have ≥1 topic (resumable runs).',
        )
        parser.add_argument(
            '--replace',
            action='store_true',
            help="Clear each book's genres/topics before tagging (default: enrich).",
        )

    def handle(self, *args, **opts):
        from plugins.installed.book_product.models import BookProduct, Genre, Topic

        apply = bool(opts['apply'])
        replace = bool(opts['replace'])

        try:
            from plugins.installed.ai_assistant.services.llm import get_llm

            llm = get_llm()
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(self.style.ERROR(f'AI provider unavailable: {exc}'))
            return

        qs = (
            BookProduct.objects.select_related('product')
            .filter(product__status='active')
            .order_by('product__created_at')
        )
        if opts['only_missing_topics']:
            qs = qs.filter(topics__isnull=True)
        books = list(qs.distinct())
        if opts['limit']:
            books = books[: opts['limit']]

        self.stdout.write(
            f'{"APPLY" if apply else "DRY-RUN"}: classifying {len(books)} books '
            f'(batch {opts["batch_size"]}, {"replace" if replace else "enrich"})…'
        )

        genre_cache: dict[str, object] = {}
        topic_cache: dict[str, object] = {}
        tagged = errors = 0

        for start in range(0, len(books), opts['batch_size']):
            batch = books[start : start + opts['batch_size']]
            try:
                results = self._classify_batch(llm, batch)
            except Exception as exc:  # noqa: BLE001 — one batch must not kill the run
                errors += 1
                self.stderr.write(self.style.WARNING(f'  batch @{start} failed: {str(exc)[:120]}'))
                continue

            for book, res in zip(batch, results, strict=False):
                genres = [self._clean(g) for g in (res.get('genres') or [])][:3]
                topics = [self._clean(t) for t in (res.get('topics') or [])][:4]
                genres = [g for g in genres if g]
                topics = [t for t in topics if t]
                self.stdout.write(
                    f'  · {book.product.name[:48]:48}  genres={genres}  topics={topics}'
                )
                if not apply:
                    continue
                if replace:
                    book.genres.clear()
                    book.topics.clear()
                for name in genres:
                    book.genres.add(self._term(Genre, name, genre_cache))
                for name in topics:
                    book.topics.add(self._term(Topic, name, topic_cache))
                tagged += 1

        style = self.style.SUCCESS if apply else self.style.WARNING
        self.stdout.write(
            style(
                f'Done. {tagged} books tagged, {errors} batch errors. '
                f'{"" if apply else "(dry-run — re-run with --apply)"}'
            )
        )

    def _classify_batch(self, llm, batch) -> list[dict]:
        lines = []
        for i, book in enumerate(batch, 1):
            author = (book.author or '').strip()
            synopsis = (book.synopsis or '').strip().replace('\n', ' ')[:240]
            byline = f' by {author}' if author else ''
            tail = f' — {synopsis}' if synopsis else ''
            lines.append(f'{i}. "{book.product.name}"{byline}{tail}')

        prompt = (
            'Classify each book into genres and topics.\n\n'
            'GENRES — choose 1-3 that best fit, using the EXACT spelling from this '
            'controlled list; only invent a new genre if none fit:\n'
            f'{", ".join(GENRE_VOCAB)}\n\n'
            'TOPICS — 2-4 specific subjects/themes (e.g. "Seafaring", "Grief", '
            '"The French Revolution", "Coming of Age"). Title-case, concise.\n\n'
            'Books:\n' + '\n'.join(lines) + '\n\n'
            'Return STRICT JSON: an array with one object per book, in order, '
            'nothing else:\n'
            '[{"i":1,"genres":["Classics","Adventure"],"topics":["Whaling","Obsession"]}]'
        )
        raw = llm.complete(prompt, system=_SYSTEM, temperature=0.2, max_tokens=1200)

        from core.llm_parsing import parse_llm_json

        data = parse_llm_json(raw or '')
        if not isinstance(data, list):
            raise ValueError(f'non-list response: {str(raw)[:80]}')
        # Map by 'i' so a misordered/short response still aligns per book.
        by_i = {int(d.get('i', n + 1)): d for n, d in enumerate(data) if isinstance(d, dict)}
        return [by_i.get(n + 1, {}) for n in range(len(batch))]

    @staticmethod
    def _clean(name) -> str:
        return (str(name or '').strip())[:60]

    @staticmethod
    def _term(model, name: str, cache: dict):
        key = slugify(name)
        if key in cache:
            return cache[key]
        obj, _ = model.objects.get_or_create(slug=key, defaults={'name': name})
        cache[key] = obj
        return obj
