"""The shared journal must not fall back to one store's sample essays.

The storefront shell carried three hardcoded dot books essays ("The case for
the small press…", Cusk and Sebald, "books we haven't read") and served them
whenever a slug was not a CMS page. On the travel and herbal stores those URLs
500'd — the dicts lacked `published_at`, which every theme's
`modified=entry.updated_at|default:entry.published_at` resolves eagerly — and
where they did render, a bookshop's essays appeared under another brand.
dotbooks keeps them: they are CMS pages there.
"""

from __future__ import annotations

from django.test import TestCase

_OLD_SAMPLE_SLUGS = (
    'a-short-note-on-patience',
    'why-we-dont-carry-books-we-havent-read',
    'the-case-for-the-small-press',
)


class JournalNoSeededPostsTests(TestCase):
    def setUp(self) -> None:
        # Stores created before v0.75.22 got these as published pages from cms
        # 0004; a store that is not a bookshop retires them (booking_marketplace's
        # seed_journal_montenegro drafts them by slug). The shell must not bring
        # them back.
        from plugins.installed.cms.models import Page

        Page.objects.filter(slug__in=_OLD_SAMPLE_SLUGS).update(state='draft')

    def test_sample_slugs_are_not_pages(self) -> None:
        for slug in _OLD_SAMPLE_SLUGS:
            with self.subTest(slug=slug):
                self.assertEqual(self.client.get(f'/journal/{slug}/').status_code, 404)
                self.assertEqual(self.client.get(f'/journal/{slug}/amp/').status_code, 404)

    def test_empty_journal_lists_no_sample_posts(self) -> None:
        for path in ('/journal/', '/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                body = response.content.decode()
                for slug in _OLD_SAMPLE_SLUGS:
                    self.assertNotIn(f'/journal/{slug}/', body)


class SampleEssaySeedTests(TestCase):
    def test_a_fresh_store_gets_the_sample_essays_as_drafts(self) -> None:
        # cms 0004 seeds them so the merchant has something to edit; published,
        # one bookshop's essays went live on every new store under its brand.
        from plugins.installed.cms.models import Page

        seeded = Page.objects.filter(slug__in=_OLD_SAMPLE_SLUGS, metadata__source='seed')
        self.assertEqual(seeded.count(), len(_OLD_SAMPLE_SLUGS))
        self.assertEqual(set(seeded.values_list('state', flat=True)), {'draft'})
