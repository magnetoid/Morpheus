"""What the Help page says about an app without anyone writing it down."""

from __future__ import annotations

from unittest import mock

from django.test import TestCase

from core.hooks import MorpheusEvents
from plugins import app_help
from plugins.installed.release_notes.help_facts import SLOT_WORDS, facts
from plugins.installed.release_notes.help_markers import Link, ask_list
from plugins.registry import app_registry


class FactsTests(TestCase):
    def test_where_reviews_are_and_what_linda_can_do_there(self):
        f = facts('reviews')
        self.assertEqual(f['label'], 'Reviews')
        self.assertTrue(f['active'])
        self.assertIn(Link('Products › Reviews', '/dashboard/reviews/'), f['places'])
        self.assertEqual(
            {t['name']: t['asks_first'] for t in f['tools']},
            {'reviews.list_pending': False, 'reviews.approve': True, 'reviews.delete': True},
        )
        self.assertEqual(f['shop'], ['the product page, under the buy form'])
        self.assertEqual(f['requires'], ['catalog', 'orders'])
        self.assertIn(MorpheusEvents.ACTIVITY_FEED, f['events'])
        self.assertIn('/dashboard/reviews/', f['urls'])
        self.assertIn('/reviews/', f['urls'])

    def test_an_apps_settings_are_a_place(self):
        self.assertIn(
            Link('Settings › Marketing › Newsletter', '/dashboard/settings/newsletter/'),
            facts('newsletter')['places'],
        )

    def test_what_needs_an_app(self):
        self.assertIn('reviews', facts('catalog')['required_by'])

    def test_an_app_that_is_off_lists_its_places_without_links(self):
        app_registry.deactivate('reviews')
        self.addCleanup(app_registry.activate, 'reviews')
        f = facts('reviews')
        self.assertFalse(f['active'])
        self.assertTrue(f['places'])
        self.assertTrue(all(p.url == '' and p.off for p in f['places']))

    def test_an_app_whose_pages_raise_still_has_facts(self):
        inst = app_registry.get('reviews')
        with mock.patch.object(
            type(inst), 'contribute_dashboard_pages', side_effect=RuntimeError('boom')
        ):
            f = facts('reviews')
        self.assertEqual(f['places'], [])
        self.assertEqual(f['label'], 'Reviews')

    def test_no_such_app(self):
        self.assertIsNone(facts('no_such_app'))


class SlotWordsTests(TestCase):
    def test_every_slot_an_app_fills_has_plain_words(self):
        slots = {b.slot for b in app_registry._storefront_blocks}
        for name in app_help.tree_apps():
            inst = app_help.load_manifest(name)
            if inst is not None:
                slots |= {b.slot for b in ask_list(inst, 'contribute_storefront_blocks')}
        self.assertEqual(sorted(slots - set(SLOT_WORDS)), [])
