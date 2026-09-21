"""journal journal_dict — SEO enrichment (cover image, author, dateModified)."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.test import TestCase

from plugins.installed.cms.models import Page
from plugins.installed.cms.services import journal_dict


class JournalDictSeoTests(TestCase):
    def test_extracts_first_body_image_and_author(self):
        page = Page.objects.create(
            slug='note',
            title='A Note',
            state='published',
            body='<p>Hi</p><img src="/media/cover.jpg" alt="c"><p>Bye</p>',
            metadata={'category': 'journal', 'author': 'Jane Doe'},
        )
        d = journal_dict(page)
        # Relative media paths are absolutized for og:image (scrapers require it).
        self.assertTrue(d['image'].startswith('https://'))
        self.assertTrue(d['image'].endswith('/media/cover.jpg'))
        self.assertEqual(d['author'], 'Jane Doe')
        self.assertIsNotNone(d['updated_at'])

    def test_explicit_cover_metadata_wins_over_body_image(self):
        page = Page.objects.create(
            slug='note2',
            title='N2',
            state='published',
            body='<img src="/media/body.jpg">',
            metadata={'category': 'journal', 'cover': '/media/explicit.jpg'},
        )
        image = journal_dict(page)['image']
        self.assertTrue(image.startswith('https://'))
        self.assertTrue(image.endswith('/media/explicit.jpg'))

    def test_author_falls_back_to_store_name(self):
        # The default byline derives from the store's own name, not a
        # hardcoded brand (generic-platform genericity).
        from core.models import StoreSettings

        StoreSettings.objects.create(store_name='Acme Books')
        page = Page.objects.create(slug='n3', title='N3', state='published', body='x', metadata={})
        self.assertEqual(journal_dict(page)['author'], 'Acme Books staff')

    def test_date_label_shows_real_publish_date_and_read_time(self):
        from datetime import UTC, datetime

        page = Page.objects.create(
            slug='n4',
            title='N4',
            state='published',
            body='<p>' + ('word ' * 400) + '</p>',  # ~400 words → 2 min read
            publish_at=datetime(2026, 7, 3, 9, 0, tzinfo=UTC),
            metadata={'category': 'journal'},
        )
        d = journal_dict(page)
        # Real date (was "%B · %-d min read" — day-of-month posing as read time).
        self.assertEqual(d['date_label'], 'July 3, 2026 · 2 min read')
        self.assertEqual(d['published_at'], page.publish_at)


class JournalDuplicateHeadingTests(TestCase):
    """A body authored as a full document repeats the title the template renders.

    19 live journal articles shipped two `<h1>` elements and the byline twice
    because of this. The audit blamed the template wrapper; the template has
    exactly one `<h1>` and it is the FIRST of the two — the duplicate is in the
    stored body, so demoting the template heading would have left the raw one.
    """

    def _page(self, body: str, slug: str = 'dup'):
        return Page.objects.create(
            slug=slug,
            title='Montenegro Family Itinerary',
            state='published',
            body=body,
            metadata={'category': 'journal', 'author': 'Djokic'},
        )

    def test_strips_leading_h1_and_the_byline_under_it(self):
        page = self._page(
            '<h1>Montenegro Family Itinerary</h1>\n'
            '<p><strong>By Djokic</strong></p>\n'
            '<p>Real body text starts here.</p>'
        )
        body = journal_dict(page)['body']
        self.assertNotIn('<h1', body)
        self.assertNotIn('By Djokic', body)
        self.assertIn('Real body text starts here.', body)

    def test_leaves_a_body_that_does_not_open_with_a_heading_alone(self):
        page = self._page('<p>by the sea, the light changes.</p><h2>Later</h2>', slug='dup2')
        self.assertEqual(
            journal_dict(page)['body'], '<p>by the sea, the light changes.</p><h2>Later</h2>'
        )

    def test_a_first_paragraph_survives_when_no_heading_preceded_it(self):
        # The byline strip is conditional on an h1 having just been removed;
        # otherwise a paragraph merely starting with "by" would vanish.
        page = self._page('<h2>Sub</h2><p>By the way, this stays.</p>', slug='dup3')
        self.assertIn('By the way, this stays.', journal_dict(page)['body'])

    def test_word_count_measures_what_the_page_renders(self):
        page = self._page('<h1>Montenegro Family Itinerary</h1><p>one two three</p>', slug='dup4')
        self.assertEqual(journal_dict(page)['word_count'], 3)


class JournalFaqPairsTests(TestCase):
    """FAQPage is built only from H2s that are genuinely questions."""

    def _pairs(self, body: str):
        from plugins.installed.cms.services import journal_faq_pairs

        return journal_faq_pairs(body)

    def test_question_headings_become_pairs(self):
        pairs = self._pairs(
            '<h2>Why visit Montenegro with children?</h2>'
            f'<p>{"Short drives and calm beaches. " * 3}</p>'
            '<h2>Best beaches for families</h2>'
            f'<p>{"Jaz and Ploce are the usual picks. " * 3}</p>'
            '<h2>Is Montenegro expensive?</h2>'
            f'<p>{"Cheaper than Croatia outside August. " * 3}</p>'
        )
        self.assertEqual(
            [p['q'] for p in pairs],
            ['Why visit Montenegro with children?', 'Is Montenegro expensive?'],
        )
        # The noun-phrase heading is skipped: calling it a Question would
        # publish a claim the page never makes.
        self.assertNotIn('Best beaches for families', [p['q'] for p in pairs])

    def test_a_single_question_is_not_an_faq(self):
        self.assertEqual(self._pairs('<h2>Only one?</h2><p>' + 'x' * 80 + '</p>'), [])

    def test_headings_with_no_real_answer_are_dropped(self):
        self.assertEqual(self._pairs('<h2>A?</h2><p>tiny</p><h2>B?</h2><p>also tiny</p>'), [])

    def test_long_answers_are_cut_on_a_sentence_boundary(self):
        body = '<h2>Q one?</h2><p>' + ('A full sentence here. ' * 60) + '</p>'
        body += '<h2>Q two?</h2><p>' + ('Another full sentence. ' * 60) + '</p>'
        for pair in self._pairs(body):
            self.assertTrue(pair['a'].endswith('.'), pair['a'][-40:])

    def test_an_article_with_no_questions_emits_nothing(self):
        page = Page.objects.create(
            slug='no-q',
            title='No questions',
            state='published',
            body='<h2>Beaches</h2><p>' + 'x' * 80 + '</p><h2>Food</h2><p>' + 'y' * 80 + '</p>',
            metadata={'category': 'journal'},
        )
        self.assertEqual(journal_dict(page)['faq_pairs'], [])
