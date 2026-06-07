"""CMS GraphQL — page CRUD plus journal-specific publishing surface."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from api.graphql_permissions import PermissionDenied
from plugins.installed.cms.graphql.queries import CmsMutationExtension, CmsPageInput, CmsQueryExtension
from plugins.installed.cms.models import Page


class _Info:
    """Minimal stand-in for strawberry.Info — only .context['request'] is read."""

    def __init__(self, *, staff: bool):
        req = RequestFactory().post('/graphql/')
        req.user = get_user_model().objects.create_user(
            username=f'gqlu-{"staff" if staff else "user"}',
            email=f'{"staff" if staff else "user"}@example.test',
            password='pw',
            is_staff=staff,
        )
        self.context = {'request': req}


class CmsGraphQLTests(TestCase):
    def test_staff_can_create_journal_page_with_metadata_and_publish_at(self):
        info = _Info(staff=True)

        created = CmsMutationExtension().create_page(
            info,
            CmsPageInput(
                title='Journal Note',
                slug='journal-note',
                excerpt='Short note',
                body='<p>Hello</p>',
                state='published',
                layout='long_form',
                metadata={'category': 'journal', 'author': 'Marko'},
                publish_at='2026-06-07T12:34:56+00:00',
            ),
        )

        page = Page.objects.get(slug='journal-note')
        self.assertEqual(created.slug, 'journal-note')
        self.assertEqual(page.metadata.get('category'), 'journal')
        self.assertEqual(page.metadata.get('author'), 'Marko')
        self.assertIsNotNone(page.publish_at)
        self.assertEqual(page.publish_at.isoformat(), '2026-06-07T12:34:56+00:00')

    def test_staff_can_query_journal_entries(self):
        Page.objects.create(
            slug='journal-live',
            title='Journal Live',
            excerpt='E',
            body='<p>Body</p>',
            state='published',
            metadata={'category': 'journal', 'author': 'Marko'},
        )
        Page.objects.create(
            slug='normal-page',
            title='Normal Page',
            body='<p>Body</p>',
            state='published',
            metadata={'category': 'page'},
        )
        Page.objects.create(
            slug='journal-draft',
            title='Journal Draft',
            body='<p>Body</p>',
            state='draft',
            metadata={'category': 'journal'},
        )

        entries = CmsQueryExtension().journal_entries(_Info(staff=True))
        slugs = [e.slug for e in entries]
        self.assertIn('journal-live', slugs)
        self.assertNotIn('normal-page', slugs)
        self.assertNotIn('journal-draft', slugs)
        live_entry = next(e for e in entries if e.slug == 'journal-live')
        self.assertEqual(live_entry.author, 'Marko')

    def test_staff_can_query_single_journal_entry(self):
        Page.objects.create(
            slug='single-journal',
            title='Single Journal',
            excerpt='Excerpt',
            body='<p>Hello</p><img src="/media/cover.jpg">',
            state='published',
            metadata={'category': 'journal', 'author': 'Marko'},
        )

        entry = CmsQueryExtension().journal_entry(_Info(staff=True), 'single-journal')
        self.assertIsNotNone(entry)
        self.assertEqual(entry.slug, 'single-journal')
        self.assertEqual(entry.author, 'Marko')
        self.assertEqual(entry.image, '/media/cover.jpg')

    def test_non_staff_cannot_create_page(self):
        with self.assertRaises(PermissionDenied):
            CmsMutationExtension().create_page(
                _Info(staff=False),
                CmsPageInput(title='Nope', slug='nope'),
            )
