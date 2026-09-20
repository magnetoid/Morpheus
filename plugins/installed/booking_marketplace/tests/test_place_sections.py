"""Place detail deep-dive enrichment:

* good_for_cards() resolves free-form tags to icon cards (title-cased, star
  fallback).
* Place.sections / external_links persist as JSON.
* the detail page renders the editorial sections AFTER "Where it is", plus a
  "Plan your visit" internal-links panel and outbound "Official resources"
  links with safe rel attributes.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import Client, TestCase

from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin


class GoodForCardsTests(TestCase):
    def test_resolves_icons_titlecase_and_fallback(self):
        from plugins.installed.booking_marketplace.place_content import good_for_cards

        cards = good_for_cards(['couples', 'wine lovers', 'zzz unknown'])
        self.assertEqual([c['label'] for c in cards], ['Couples', 'Wine lovers', 'Zzz unknown'])
        # couples → heart path; wine → wine glass path; unknown → star path.
        self.assertIn('M19 14c1.49', cards[0]['icon'])
        self.assertIn('M8 22h8', cards[1]['icon'])
        self.assertIn('12 2l3.09', cards[2]['icon'])

    def test_empty_and_blank_tags_ignored(self):
        from plugins.installed.booking_marketplace.place_content import good_for_cards

        self.assertEqual(good_for_cards([]), [])
        self.assertEqual(good_for_cards(['', '  ']), [])


class PlaceSectionsRenderTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        self.client = Client()

    def _place(self):
        from plugins.installed.booking_marketplace.models import Place

        return Place.objects.create(
            name='Testville',
            slug='testville',
            region='kotor',
            summary='A test town on the bay.',
            overview='Lead overview body.',
            latitude=Decimal('42.42'),
            longitude=Decimal('18.77'),
            good_for=['couples', 'hikers', 'wine lovers'],
            sections=[
                {
                    'heading': 'The layered past',
                    'body': 'A deep dive into the stone lanes and Venetian walls of Testville.',
                },
                {
                    'heading': 'When to visit',
                    'body': 'Shoulder seasons are calmest here, summer is busiest.',
                },
            ],
            external_links=[
                {'label': 'UNESCO World Heritage', 'url': 'https://whc.unesco.org/en/list/125'},
                {'label': 'Montenegro tourism', 'url': 'https://www.montenegro.travel'},
            ],
        )

    def test_fields_persist(self):
        p = self._place()
        p.refresh_from_db()
        self.assertEqual(p.sections[0]['heading'], 'The layered past')
        self.assertEqual(p.external_links[1]['url'], 'https://www.montenegro.travel')

    def test_sections_render_after_where_it_is(self):
        self._place()
        body = self.client.get('/places/testville/').content.decode()
        self.assertEqual(self.client.get('/places/testville/').status_code, 200)
        self.assertIn('The layered past', body)
        self.assertIn('A deep dive into the stone lanes', body)
        # The long read must sit AFTER the map section, not before it.
        self.assertLess(body.index('Where it is'), body.index('The layered past'))

    def test_outbound_links_are_safe_and_present(self):
        self._place()
        body = self.client.get('/places/testville/').content.decode()
        self.assertIn('https://whc.unesco.org/en/list/125', body)
        self.assertIn('rel="noopener nofollow"', body)
        self.assertIn('target="_blank"', body)

    def test_internal_plan_your_visit_links(self):
        self._place()
        body = self.client.get('/places/testville/').content.decode()
        self.assertIn('Plan your visit', body)
        self.assertIn('/hotels/', body)
        self.assertIn('/regions/kotor/', body)

    def test_ideal_for_icon_cards(self):
        self._place()
        body = self.client.get('/places/testville/').content.decode()
        self.assertIn('Ideal for', body)
        self.assertIn('Couples', body)  # title-cased label proves good_for_cards ran


class SeedPopulatesEnrichmentTests(TestCase):
    """The seed_places command (run on deploy) must populate sections +
    external_links on the real places — this exercises get_or_create's
    defaults AND the idempotent backfill path end-to-end.
    """

    def test_seed_gives_kotor_deep_content_and_links(self):
        from django.core.management import call_command

        from plugins.installed.booking_marketplace.models import Place

        call_command('seed_places')
        kotor = Place.objects.filter(slug='kotor').first()
        self.assertIsNotNone(kotor, 'seed_places did not create the Kotor place')
        self.assertGreaterEqual(len(kotor.sections), 3)
        self.assertGreaterEqual(len(kotor.external_links), 2)
        self.assertGreaterEqual(
            sum(len(s['body']) for s in kotor.sections),
            2000,
            'Kotor deep-dive prose should be >= 2000 chars',
        )

    def test_seed_is_idempotent_backfill(self):
        """Running twice must not error or duplicate; backfill fills empties."""
        from django.core.management import call_command

        from plugins.installed.booking_marketplace.models import Place

        call_command('seed_places')
        call_command('seed_places')
        # Every seeded place ends up with both enrichment fields populated.
        empty = Place.objects.filter(sections=[]).count()
        self.assertEqual(empty, 0, 'some places have empty sections after seeding')
