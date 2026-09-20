"""Places enrichment — model fields, JSON-LD, views, seed content, SEO/AEO."""

import json
from decimal import Decimal

from django.test import RequestFactory, TestCase


class PlaceFieldTests(TestCase):
    def test_new_content_fields_persist(self):
        from plugins.installed.booking_marketplace.models import Place

        p = Place.objects.create(
            name='Kotor',
            slug='kotor-test',
            region='kotor',
            place_type='coastal',
            summary='A fortified medieval old town.',
            description='Lead paragraph.',
            overview='A much longer editorial body about Kotor that adds real depth.',
            faqs=[
                {
                    'q': 'Is Kotor worth visiting?',
                    'a': 'Yes — the walled old town and bay are unmissable.',
                }
            ],
            quick_facts=[{'label': 'Best time', 'value': 'May–Jun, Sep'}],
            good_for=['couples', 'history lovers'],
            latitude=Decimal('42.424200'),
            longitude=Decimal('18.771200'),
        )
        p.refresh_from_db()
        self.assertEqual(
            p.overview, 'A much longer editorial body about Kotor that adds real depth.'
        )
        self.assertEqual(p.faqs[0]['q'], 'Is Kotor worth visiting?')
        self.assertEqual(p.quick_facts[0]['label'], 'Best time')
        self.assertIn('couples', p.good_for)
        self.assertEqual(p.latitude, Decimal('42.424200'))

    def test_content_fields_default_empty(self):
        from plugins.installed.booking_marketplace.models import Place

        p = Place.objects.create(name='Bar', slug='bar-test', region='ulcinj')
        self.assertEqual(p.overview, '')
        self.assertEqual(p.faqs, [])
        self.assertEqual(p.quick_facts, [])
        self.assertEqual(p.good_for, [])
        self.assertIsNone(p.latitude)


class PlaceJsonLdTests(TestCase):
    def setUp(self):
        from plugins.installed.booking_marketplace.models import Place

        self.place = Place.objects.create(
            name='Kotor',
            slug='kotor-jld',
            region='kotor',
            place_type='coastal',
            summary='A fortified medieval old town.',
            overview='A longer body.',
            image=None,
            faqs=[
                {
                    'q': 'Is Kotor worth visiting?',
                    'a': 'Absolutely — the old town and bay are unmissable.',
                },
                {'q': 'When should I go?', 'a': 'Late spring or early autumn.'},
            ],
            latitude=Decimal('42.424200'),
            longitude=Decimal('18.771200'),
        )
        self.factory = RequestFactory()

    def test_place_jsonld_graph(self):
        from plugins.installed.booking_marketplace import seo_jsonld

        req = self.factory.get('/places/kotor-jld/')
        data = json.loads(seo_jsonld.place_jsonld(self.place, request=req))
        types = [n['@type'] for n in data['@graph']]
        self.assertIn('TouristDestination', types)
        self.assertIn('FAQPage', types)
        self.assertIn('BreadcrumbList', types)
        dest = next(n for n in data['@graph'] if n['@type'] == 'TouristDestination')
        self.assertEqual(dest['name'], 'Kotor')
        self.assertIn('geo', dest)
        self.assertTrue(dest['url'].startswith('http'))
        self.assertEqual(dest['address']['addressCountry'], 'ME')
        faq = next(n for n in data['@graph'] if n['@type'] == 'FAQPage')
        self.assertEqual(len(faq['mainEntity']), 2)

    def test_place_jsonld_omits_faq_and_geo_when_absent(self):
        from plugins.installed.booking_marketplace import seo_jsonld
        from plugins.installed.booking_marketplace.models import Place

        p = Place.objects.create(name='Bar', slug='bar-jld', region='ulcinj')
        data = json.loads(seo_jsonld.place_jsonld(p, request=self.factory.get('/places/bar-jld/')))
        types = [n['@type'] for n in data['@graph']]
        self.assertIn('TouristDestination', types)
        self.assertNotIn('FAQPage', types)
        dest = next(n for n in data['@graph'] if n['@type'] == 'TouristDestination')
        self.assertNotIn('geo', dest)

    def test_index_jsonld_item_list(self):
        from plugins.installed.booking_marketplace import seo_jsonld
        from plugins.installed.booking_marketplace.models import Place

        p2 = Place.objects.create(name='Budva', slug='budva-jld', region='budva')
        data = json.loads(
            seo_jsonld.places_index_jsonld([self.place, p2], request=self.factory.get('/places/'))
        )
        types = [n['@type'] for n in data['@graph']]
        self.assertIn('ItemList', types)
        self.assertIn('BreadcrumbList', types)
        il = next(n for n in data['@graph'] if n['@type'] == 'ItemList')
        self.assertEqual(len(il['itemListElement']), 2)


class PlaceViewTests(TestCase):
    def setUp(self):
        from plugins.installed.booking_marketplace.models import Place

        self.place = Place.objects.create(
            name='Kotor',
            slug='kotor-view',
            region='kotor',
            place_type='coastal',
            summary='A fortified medieval old town.',
            description='The lead paragraph.',
            overview='An extended editorial body about Kotor with real depth and detail.',
            highlights=['Old Town walls', 'Fortress hike'],
            faqs=[{'q': 'Is Kotor worth visiting?', 'a': 'Absolutely — a must-see.'}],
            quick_facts=[{'label': 'Best time', 'value': 'May–Jun, Sep'}],
            good_for=['couples', 'history lovers'],
            latitude=Decimal('42.424200'),
            longitude=Decimal('18.771200'),
        )

    def test_detail_renders_enriched_sections_and_jsonld(self):
        resp = self.client.get('/places/kotor-view/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('An extended editorial body about Kotor', html)  # overview
        self.assertIn('Best time', html)  # quick_facts label
        self.assertIn('Is Kotor worth visiting?', html)  # FAQ question
        self.assertIn('History lovers', html)  # good_for → Ideal-for icon card (title-cased)
        self.assertIn('application/ld+json', html)  # structured data present
        self.assertIn('TouristDestination', html)
        self.assertIn('place-map', html)  # map (has coords)

    def test_detail_feeds_per_place_meta_description(self):
        # place_detail passes seo_description=summary → the shared seo_meta emits it.
        resp = self.client.get('/places/kotor-view/')
        self.assertContains(resp, 'A fortified medieval old town')

    def test_index_groups_by_region_with_jsonld(self):
        resp = self.client.get('/places/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('Kotor Bay', html)  # REGIONS label for 'kotor'
        self.assertIn('Kotor', html)  # the place card
        self.assertIn('application/ld+json', html)
        self.assertIn('ItemList', html)

    def test_script_tag_not_breakable_by_content(self):
        from plugins.installed.booking_marketplace.models import Place

        p = Place.objects.create(
            name='Budva</script><script>alert(1)</script>',
            slug='budva-breakout',
            region='budva',
        )
        resp = self.client.get(f'/places/{p.slug}/')
        self.assertNotContains(resp, '<script>alert')
