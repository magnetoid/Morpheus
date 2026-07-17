"""Landing-page intro copy for the book taxonomies.

Two bugs are pinned here:

* ``/genres/`` and ``/topics/`` could not hold intro copy at all — the view
  hardcoded ``root: None``, the model's choices omitted genre/topic so no
  BookTaxonomyRoot row could exist, and the dashboard hid the "Edit landing
  page" button for exactly those two. All three layers had to open.
* The per-page Generate button and the bulk backfill each built their own
  prompt; they now share ``services_copy`` so the copy matches.
"""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from plugins.installed.book_product.models import (
    BookProduct,
    BookRootTaxonomy,
    BookTaxonomy,
    BookTaxonomyRoot,
    Genre,
    Topic,
)
from plugins.installed.catalog.models import Product


def _staff_client(username: str) -> Client:
    client = Client()
    user = get_user_model().objects.create_user(
        username=username, email=f'{username}@x.test', password='pw', is_staff=True
    )
    client.force_login(user)
    return client


class RootTaxonomyChoicesTests(TestCase):
    def test_curated_kinds_can_have_a_root_but_not_a_term(self):
        """Genre/Topic index pages need a root row; their TERMS carry their own
        SEO on the model, so they must stay out of BookTaxonomy."""
        self.assertIn('genre', BookRootTaxonomy.values)
        self.assertIn('topic', BookRootTaxonomy.values)
        self.assertNotIn('genre', BookTaxonomy.values)
        self.assertNotIn('topic', BookTaxonomy.values)

    def test_every_term_kind_is_also_a_root_kind(self):
        self.assertTrue(set(BookTaxonomy.values).issubset(set(BookRootTaxonomy.values)))

    def test_genre_root_row_is_storable(self):
        root = BookTaxonomyRoot.objects.create(taxonomy='genre', description='Our shelves.')
        root.full_clean()  # would raise on an invalid choice
        self.assertEqual(BookTaxonomyRoot.objects.get(taxonomy='genre').description, 'Our shelves.')


class CuratedRootRendersIntroTests(TestCase):
    """The storefront /genres/ + /topics/ pages must render their intro."""

    def setUp(self):
        # Product.sku is unique — an omitted sku defaults to '' and the second
        # fixture collides, so every fixture below names one.
        product = Product.objects.create(
            name='A Book', slug='a-book', sku='TAX-1', price=5, status='active'
        )
        book = BookProduct.objects.create(product=product)
        self.genre = Genre.objects.create(name='Fiction', slug='fiction')
        self.topic = Topic.objects.create(name='Love', slug='love')
        book.genres.add(self.genre)
        book.topics.add(self.topic)

    def test_genres_index_renders_root_description(self):
        BookTaxonomyRoot.objects.create(
            taxonomy='genre',
            description='Every genre we shelve, from the well-trodden to the odd.',
            meta_description='Genres at dot books.',
        )
        resp = self.client.get('/genres/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('Every genre we shelve', html)
        self.assertIn('Genres at dot books.', html)

    def test_topics_index_renders_root_description(self):
        BookTaxonomyRoot.objects.create(taxonomy='topic', description='Themes, not shelves.')
        resp = self.client.get('/topics/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Themes, not shelves.', resp.content.decode())

    def test_index_without_a_root_still_renders(self):
        resp = self.client.get('/genres/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Fiction', resp.content.decode())


class CuratedRootDashboardTests(TestCase):
    def setUp(self):
        self.client = _staff_client('taxstaff')
        Genre.objects.create(name='Fiction', slug='fiction')

    def test_landing_editor_saves_a_genre_root(self):
        url = reverse('book_product_dashboard:taxonomy_root_edit', args=['genre'])
        self.assertEqual(self.client.get(url).status_code, 200)
        resp = self.client.post(url, {'description': 'Shelf notes.', 'meta_title': 'Genres'})
        self.assertEqual(resp.status_code, 302)
        root = BookTaxonomyRoot.objects.get(taxonomy='genre')
        self.assertEqual(root.description, 'Shelf notes.')

    def test_taxonomies_list_offers_a_landing_editor_for_curated_kinds(self):
        resp = self.client.get(reverse('book_product_dashboard:taxonomies'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        for kind in ('genre', 'topic'):
            self.assertIn(
                reverse('book_product_dashboard:taxonomy_root_edit', args=[kind]),
                html,
                f'{kind} landing-page editor should be reachable from the list',
            )

    def test_unknown_root_kind_is_rejected(self):
        resp = self.client.post(
            '/dashboard/book-taxonomies/nonsense/landing/', {'description': 'x'}
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(BookTaxonomyRoot.objects.filter(taxonomy='nonsense').exists())


class BulkCopyBackfillTests(TestCase):
    """The backfill writes the pages that matter and never clobbers hand copy."""

    def setUp(self):
        self.stocked, self.bare = [], []
        for i in range(3):
            product = Product.objects.create(
                name=f'Book {i}', slug=f'book-{i}', sku=f'BULK-{i}', price=5, status='active'
            )
            book = BookProduct.objects.create(product=product)
            genre = Genre.objects.create(name=f'Genre {i}', slug=f'genre-{i}')
            book.genres.add(genre)
            self.stocked.append(genre)
        # A genre with no books — its page would be bare, so skip it.
        self.empty = Genre.objects.create(name='Unused', slug='unused')

    # Realistic length on purpose: the backfill refuses to auto-publish an
    # answer too short to be the 2-3 sentence intro it asked for, so a toy
    # fixture would be rejected and test nothing.
    FAKE_INTRO = 'Novels that argue with the reader, from Melville to the present day.'

    def _fake_copy(self, *args, **kwargs):
        return {
            'description': self.FAKE_INTRO,
            'meta_title': 'Gen',
            'meta_description': 'Meta.',
        }

    def test_writes_only_stocked_terms_missing_copy(self):
        from plugins.installed.book_product.tasks import backfill_taxonomy_copy

        with patch(
            'plugins.installed.book_product.services_copy.generate_copy',
            side_effect=self._fake_copy,
        ):
            result = backfill_taxonomy_copy('genre', limit=50)
        self.assertEqual(result['written'], 3)
        self.empty.refresh_from_db()
        self.assertEqual(self.empty.description, '', 'a term with no books gets no page copy')
        for genre in self.stocked:
            genre.refresh_from_db()
            self.assertEqual(genre.description, self.FAKE_INTRO)

    def test_never_overwrites_existing_copy(self):
        from plugins.installed.book_product.tasks import backfill_taxonomy_copy

        mine = self.stocked[0]
        mine.description = 'Hand-written, do not touch.'
        mine.save()
        with patch(
            'plugins.installed.book_product.services_copy.generate_copy',
            side_effect=self._fake_copy,
        ):
            backfill_taxonomy_copy('genre', limit=50)
        mine.refresh_from_db()
        self.assertEqual(mine.description, 'Hand-written, do not touch.')

    def test_limit_is_capped_and_honoured(self):
        from plugins.installed.book_product.tasks import backfill_taxonomy_copy

        with patch(
            'plugins.installed.book_product.services_copy.generate_copy',
            side_effect=self._fake_copy,
        ):
            result = backfill_taxonomy_copy('genre', limit=1)
        self.assertEqual(result['written'], 1)

    def test_provider_failure_skips_the_row_not_the_batch(self):
        from plugins.installed.book_product.services_copy import CopyGenerationError
        from plugins.installed.book_product.tasks import backfill_taxonomy_copy

        calls = {'n': 0}

        def flaky(*args, **kwargs):
            calls['n'] += 1
            if calls['n'] == 1:
                raise CopyGenerationError('no provider')
            return self._fake_copy()

        with patch('plugins.installed.book_product.services_copy.generate_copy', side_effect=flaky):
            result = backfill_taxonomy_copy('genre', limit=50)
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(result['written'], 2)

    def test_unknown_kind_is_a_no_op(self):
        from plugins.installed.book_product.tasks import backfill_taxonomy_copy

        self.assertEqual(backfill_taxonomy_copy('nonsense')['written'], 0)


class BackfillCountHonestyTests(TestCase):
    """The button's number and the task's target set must be the SAME set.

    They were computed from different predicates: the dashboard counted any
    term with books (any status) lacking SEO, while the task only writes terms
    with ACTIVE books lacking a description. A genre whose books were all
    drafts was advertised as a missing intro the task would never write — the
    count never moved however often you clicked.
    """

    def setUp(self):
        self.client = _staff_client('countstaff')
        # Books exist, but none are active — the task will never target this.
        draft = Product.objects.create(
            name='Draft Book', slug='draft-book', sku='CNT-1', price=5, status='draft'
        )
        BookProduct.objects.create(product=draft).genres.add(
            Genre.objects.create(name='Noir', slug='noir')
        )
        # A real target: active book, no intro.
        live = Product.objects.create(
            name='Live Book', slug='live-book', sku='CNT-2', price=5, status='active'
        )
        BookProduct.objects.create(product=live).genres.add(
            Genre.objects.create(name='Westerns', slug='westerns')
        )

    def test_count_matches_what_the_task_targets(self):
        from plugins.installed.book_product.dashboard_taxonomies import _curated_groups
        from plugins.installed.book_product.tasks import missing_copy_queryset

        group = next(g for g in _curated_groups() if g['key'] == 'genre')
        self.assertEqual(group['missing_copy'], missing_copy_queryset('genre').count())
        self.assertEqual(group['missing_copy'], 1, 'only the active-book genre counts')

    def test_draft_only_genre_is_not_advertised(self):
        from plugins.installed.book_product.tasks import missing_copy_queryset

        targets = [o.slug for o in missing_copy_queryset('genre')]
        self.assertIn('westerns', targets)
        self.assertNotIn('noir', targets, 'a genre with no active books is not writable work')


class BackfillLockTests(TestCase):
    """Every term is a paid LLM call, so a re-click must not queue a second run."""

    def setUp(self):
        self.client = _staff_client('lockstaff')
        from django.core.cache import cache

        cache.delete('book_product:backfill:genre')
        product = Product.objects.create(
            name='Locked', slug='locked', sku='LCK-1', price=5, status='active'
        )
        BookProduct.objects.create(product=product).genres.add(
            Genre.objects.create(name='Essays', slug='essays')
        )

    def test_second_click_while_running_does_not_queue_again(self):
        url = reverse('book_product_dashboard:curated_backfill', args=['genre'])
        with patch('plugins.installed.book_product.tasks.backfill_taxonomy_copy.delay') as delay:
            self.client.post(url, {'limit': 5})
            self.client.post(url, {'limit': 5})
        self.assertEqual(delay.call_count, 1, 'the second click must be refused by the lock')

    def test_lock_is_released_when_the_run_finishes(self):
        from django.core.cache import cache

        from plugins.installed.book_product.tasks import backfill_taxonomy_copy

        cache.add('book_product:backfill:genre', '1', 60)
        with patch(
            'plugins.installed.book_product.services_copy.generate_copy',
            side_effect=lambda *a, **k: {
                'description': 'A long enough intro sentence for the guard.',
                'meta_title': 'E',
                'meta_description': 'M',
            },
        ):
            backfill_taxonomy_copy('genre', limit=5)
        self.assertIsNone(
            cache.get('book_product:backfill:genre'),
            'a finished run must free the lock, not hold it for the full TTL',
        )


class CopyServiceTests(TestCase):
    def test_prompt_is_grounded_in_the_actual_books(self):
        from plugins.installed.book_product.services_copy import _subject_for

        product = Product.objects.create(
            name='Tender Buttons', slug='tb', sku='COPY-1', price=5, status='active'
        )
        book = BookProduct.objects.create(product=product)
        genre = Genre.objects.create(name='Poetry', slug='poetry')
        book.genres.add(genre)
        subject, context_line = _subject_for('genre', 'poetry')
        self.assertIn('Poetry', subject)
        self.assertIn('Tender Buttons', context_line)

    def test_unknown_taxonomy_raises(self):
        from plugins.installed.book_product.services_copy import _subject_for

        with self.assertRaises(LookupError):
            _subject_for('nonsense', '')


class MalformedResponseTests(TestCase):
    """Junk must never reach a storefront page.

    A truncated reply ('{') once parsed to nothing, fell through the raw-text
    fallback, and published a literal '{' as the intro on /genre/drama/.
    """

    def setUp(self):
        product = Product.objects.create(
            name='A Play', slug='a-play', sku='MAL-1', price=5, status='active'
        )
        book = BookProduct.objects.create(product=product)
        self.genre = Genre.objects.create(name='Drama', slug='drama')
        book.genres.add(self.genre)

    def _generate_returning(self, raw):
        from plugins.installed.book_product.services_copy import generate_copy

        gateway = type('G', (), {'complete': lambda self, *a, **k: raw})()
        with patch('plugins.installed.ai_assistant.services.llm.get_llm', return_value=gateway):
            return generate_copy('genre', 'drama')

    def test_truncated_json_raises_instead_of_publishing_it(self):
        from plugins.installed.book_product.services_copy import CopyGenerationError

        with self.assertRaises(CopyGenerationError):
            self._generate_returning('{')

    def test_broken_json_raises(self):
        from plugins.installed.book_product.services_copy import CopyGenerationError

        with self.assertRaises(CopyGenerationError):
            self._generate_returning('{"description": "half a sen')

    def test_a_terse_answer_is_returned_to_the_human(self):
        """The length guard lives in the AUTO-PUBLISH path, not here: the
        dashboard's Generate button puts the result in front of a person who
        can judge it, so the service must not censor short copy."""
        self.assertEqual(
            self._generate_returning('{"description": "Drama."}')['description'], 'Drama.'
        )

    def test_backfill_refuses_to_publish_a_too_short_answer(self):
        from plugins.installed.book_product.tasks import backfill_taxonomy_copy

        gateway = type('G', (), {'complete': lambda self, *a, **k: '{"description": "Drama."}'})()
        with patch('plugins.installed.ai_assistant.services.llm.get_llm', return_value=gateway):
            result = backfill_taxonomy_copy('genre', limit=5)
        self.assertEqual(result['written'], 0)
        self.genre.refresh_from_db()
        self.assertEqual(self.genre.description, '', 'nobody reviewed this — it must not go live')

    def test_plain_prose_is_still_accepted(self):
        """A model that ignores the JSON instruction but writes real copy is
        fine — that's what the raw fallback is legitimately for."""
        prose = 'Plays that argue with the audience, from Ibsen to the present day.'
        self.assertEqual(self._generate_returning(prose)['description'], prose)

    def test_backfill_skips_a_malformed_row(self):
        from plugins.installed.book_product.tasks import backfill_taxonomy_copy

        gateway = type('G', (), {'complete': lambda self, *a, **k: '{'})()
        with patch('plugins.installed.ai_assistant.services.llm.get_llm', return_value=gateway):
            result = backfill_taxonomy_copy('genre', limit=5)
        self.assertEqual(result['written'], 0)
        self.genre.refresh_from_db()
        self.assertEqual(self.genre.description, '')
