"""journal _journal_dict — SEO enrichment (cover image, author, dateModified)."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.test import TestCase

from plugins.installed.cms.models import Page
from plugins.installed.cms.services import _journal_dict


class JournalDictSeoTests(TestCase):
    def test_extracts_first_body_image_and_author(self):
        page = Page.objects.create(
            slug='note',
            title='A Note',
            state='published',
            body='<p>Hi</p><img src="/media/cover.jpg" alt="c"><p>Bye</p>',
            metadata={'category': 'journal', 'author': 'Jane Doe'},
        )
        d = _journal_dict(page)
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
        image = _journal_dict(page)['image']
        self.assertTrue(image.startswith('https://'))
        self.assertTrue(image.endswith('/media/explicit.jpg'))

    def test_author_falls_back_to_default(self):
        page = Page.objects.create(slug='n3', title='N3', state='published', body='x', metadata={})
        self.assertEqual(_journal_dict(page)['author'], 'dot books staff')
