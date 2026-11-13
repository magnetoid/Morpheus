"""The dashboard's search box finds every part of the store: apps by name, every
field of their settings, their guides, the emails, and each app's own records.

Until v0.151.0 it read the menu and six kinds of record by name only, so
"audiobooks", "narration", "ElevenLabs" or "Turnstile" found nothing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from morpheus.core import MorpheusEvents, hook_registry
from plugins import dashboard_search as ds

BASE = Path(__file__).resolve().parents[1] / 'templates' / 'admin_dashboard' / 'base.html'


def _client():
    user = get_user_model().objects.create_user(
        username='finder', email='finder@example.com', password='x', is_staff=True
    )
    c = Client()
    c.force_login(user)
    return c


def _hits(client, q):
    return json.loads(client.get('/dashboard/palette/search/', {'q': q}).content)['hits']


def _urls(hits, section=None):
    return [h['url'] for h in hits if section is None or h['section'] == section]


class AppsSettingsAndGuidesTests(TestCase):
    def setUp(self):
        self.client = _client()

    def test_an_app_by_its_name_opens_its_settings_first(self):
        hits = _hits(self.client, 'audiobooks')
        self.assertEqual(hits[0]['section'], 'Apps')
        self.assertEqual(hits[0]['url'], '/dashboard/settings/audiobooks/')
        self.assertIn('/dashboard/help/audiobooks/', _urls(hits, 'Help'))

    def test_a_settings_field_by_its_label_opens_the_field(self):
        hits = _hits(self.client, 'elevenlabs api key')
        self.assertIn(
            '/dashboard/settings/audiobooks/#f-audiobooks-elevenlabs_api_key',
            _urls(hits, 'Settings'),
        )

    def test_an_apps_name_narrows_its_fields(self):
        urls = _urls(_hits(self.client, 'audiobooks voice'), 'Settings')
        self.assertIn('/dashboard/settings/audiobooks/#f-audiobooks-qwen_voice', urls)

    def test_accents_and_case_do_not_matter(self):
        urls = _urls(_hits(self.client, 'ÉLEVENLABS model'), 'Settings')
        self.assertIn('/dashboard/settings/audiobooks/#f-audiobooks-elevenlabs_model', urls)

    def test_one_typo_is_forgiven(self):
        self.assertIn('/dashboard/settings/audiobooks/', _urls(_hits(self.client, 'audiobok')))

    def test_a_guides_words_find_its_guide(self):
        self.assertIn(
            '/dashboard/help/audiobooks/', _urls(_hits(self.client, 'ElevenReader'), 'Help')
        )

    def test_an_app_with_only_settings_pages_opens_the_first(self):
        hits = [h for h in _hits(self.client, 'tax') if h['section'] == 'Apps']
        self.assertTrue(hits)
        self.assertEqual(hits[0]['url'], '/dashboard/tax/regions/')

    def test_a_switched_off_app_opens_its_card_in_apps(self):
        from plugins.registry import app_registry

        real = app_registry.is_active
        with patch.object(app_registry, 'is_active', side_effect=lambda n: n != 'tax' and real(n)):
            hits = [h for h in _hits(self.client, 'tax') if h['section'] == 'Apps']
        self.assertEqual(hits[0]['url'], '/dashboard/apps/#app-tax')
        self.assertIn('switched off', hits[0]['hint'])

    def test_the_apps_catalogue_has_the_anchor(self):
        body = self.client.get('/dashboard/apps/').content.decode()
        self.assertIn('id="app-tax"', body)

    def test_an_email_is_found_by_its_name(self):
        self.assertTrue(
            [h for h in _hits(self.client, 'cart abandoned email') if h['section'] == 'Emails']
        )

    def test_the_shop_search_carries_the_query_safely(self):
        shop = [h for h in _hits(self.client, 'a&b') if h['section'] == 'Storefront']
        self.assertEqual(shop[0]['url'], '/products/?q=a%26b')

    def test_every_icon_is_one_the_dashboard_draws(self):
        drawn = set(re.findall(r"'([a-z0-9-]+)':", BASE.read_text()))
        for q in ('audiobooks', 'tax', 'order', 'elevenlabs', 'stripe', 'email'):
            for h in _hits(self.client, q):
                self.assertIn(h['icon'], drawn, f'{q!r}: {h["label"]} uses {h["icon"]!r}')


class RecordsFromTheAppsTests(TestCase):
    """Every app answers DASHBOARD_SEARCH for what it owns; the shell keeps only what
    the person may open, and only dashboard addresses."""

    def setUp(self):
        self.client = _client()
        saved = list(hook_registry._handlers[MorpheusEvents.DASHBOARD_SEARCH])
        self.addCleanup(hook_registry._handlers.__setitem__, MorpheusEvents.DASHBOARD_SEARCH, saved)

    def _answer(self, *hits):
        def handler(value, **kwargs):
            value.extend(hits)
            return value

        hook_registry.register(MorpheusEvents.DASHBOARD_SEARCH, handler)

    def test_an_apps_record_is_listed(self):
        self._answer(
            ds.hit(
                section='Widgets',
                kind='widget',
                label='Blue widget',
                url='/dashboard/w/1/',
                query_words=['blue'],
            )
        )
        self.assertIn('/dashboard/w/1/', _urls(_hits(self.client, 'blue'), 'Widgets'))

    def test_a_record_the_person_may_not_open_is_left_out(self):
        self._answer(
            ds.hit(
                section='Widgets',
                kind='widget',
                label='Blue',
                url='/dashboard/w/1/',
                capability='widgets.read',
            ),
            ds.hit(section='Widgets', kind='widget', label='Blue 2', url='/dashboard/w/2/'),
        )
        palette = 'plugins.installed.admin_dashboard.views_split.palette'
        deny = patch(f'{palette}.has_capability', side_effect=lambda u, cap: cap != 'widgets.read')
        with deny, patch(f'{palette}.enforcement_mode', return_value='enforce'):
            urls = _urls(_hits(self.client, 'blue'))
        self.assertNotIn('/dashboard/w/1/', urls)
        self.assertIn('/dashboard/w/2/', urls)
        # While roles are only logged, the page would open, so the search lists it.
        with deny, patch(f'{palette}.enforcement_mode', return_value='log'):
            self.assertIn('/dashboard/w/1/', _urls(_hits(self.client, 'blue')))

    def test_an_address_outside_the_store_is_left_out(self):
        self._answer(
            ds.hit(section='Widgets', kind='widget', label='Blue', url='https://example.com/'),
            ds.hit(section='Widgets', kind='widget', label='Blue', url='//example.com/'),
        )
        self.assertFalse([h for h in _hits(self.client, 'blue') if h['section'] == 'Widgets'])

    def test_one_failing_app_does_not_empty_the_search(self):
        def broken(value, **kwargs):
            raise RuntimeError('boom')

        hook_registry.register(MorpheusEvents.DASHBOARD_SEARCH, broken)
        self.assertIn('/dashboard/settings/audiobooks/', _urls(_hits(self.client, 'audiobooks')))

    def test_records_wait_for_two_characters(self):
        calls = []

        def counting(value, **kwargs):
            calls.append(kwargs['query'])
            return value

        hook_registry.register(MorpheusEvents.DASHBOARD_SEARCH, counting)
        _hits(self.client, 'a')
        _hits(self.client, 'ab')
        self.assertEqual(calls, ['ab'])


class MatchingTests(TestCase):
    def test_fold(self):
        self.assertEqual(ds.fold('Čokolada Đurđevak'), 'cokolada durdevak')

    def test_rank_order(self):
        w = ds.words('tax')
        self.assertGreater(ds.score(w, 'Tax'), ds.score(w, 'Tax regions'))
        self.assertGreater(ds.score(w, 'Tax regions'), ds.score(w, 'Book taxonomies'))
        self.assertGreater(
            ds.score(w, 'Book taxonomies'), ds.score(w, 'Bookvault', 'Shipping & tax')
        )
        self.assertEqual(ds.score(w, 'Coupons'), 0)

    def test_a_typo_needs_five_letters(self):
        self.assertTrue(ds.score(ds.words('narrtion'), 'Narration service'))
        self.assertFalse(ds.score(ds.words('tex'), 'Tax'))

    def test_matching_needs_every_word(self):
        from plugins.installed.catalog.models import Category

        Category.objects.create(name='Science fiction', slug='sf')
        Category.objects.create(name='Science', slug='sci')
        found = Category.objects.filter(ds.matching('science fic', ['name', 'slug']))
        self.assertEqual([c.slug for c in found], ['sf'])
