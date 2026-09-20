"""seed_journal_montenegro — publishes Montenegro articles, retires core ones."""

from django.core.management import call_command
from django.test import TestCase

from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin


class JournalSeedTests(MontenegroThemeMixin, TestCase):
    def test_publishes_montenegro_and_retires_core(self):
        from plugins.installed.cms.models import Page

        # A core "dot books" journal article, published (core migration 0004 may
        # already have seeded it in the test DB — update_or_create is safe either way).
        Page.objects.update_or_create(
            slug='the-case-for-the-small-press',
            defaults={
                'title': 'The case for the small press',
                'state': 'published',
                'metadata': {'category': 'journal'},
            },
        )
        call_command('seed_journal_montenegro')

        # Core article retired (unpublished, not deleted).
        self.assertEqual(Page.objects.get(slug='the-case-for-the-small-press').state, 'draft')

        # Montenegro articles published + tagged journal.
        kotor = Page.objects.get(slug='48-hours-in-kotor')
        self.assertEqual(kotor.state, 'published')
        self.assertEqual(kotor.metadata.get('category'), 'journal')
        self.assertTrue(
            Page.objects.filter(state='published', metadata__category='journal').count() >= 6
        )

    def test_idempotent_and_leaves_user_pages_alone(self):
        from plugins.installed.cms.models import Page

        # A merchant-authored journal page must survive re-runs.
        Page.objects.create(
            slug='my-own-post',
            title='My own post',
            state='published',
            metadata={'category': 'journal'},
        )
        call_command('seed_journal_montenegro')
        call_command('seed_journal_montenegro')
        self.assertEqual(Page.objects.filter(slug='48-hours-in-kotor').count(), 1)
        self.assertEqual(Page.objects.get(slug='my-own-post').state, 'published')  # untouched
