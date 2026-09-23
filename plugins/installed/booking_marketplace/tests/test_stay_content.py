"""Data-grounded hotel copy — unique per property, invents nothing.

`stay_content` composes the "Best for" profile and the "Staying in…" intro from
a Property's own stored attributes, replacing the boilerplate paragraph that
repeated on all 68 hotels (SEO audit 2026-09, thin/duplicate hotel template).
Pure and stateless, so these run without a DB.
"""

from __future__ import annotations

from types import SimpleNamespace

from django.test import SimpleTestCase

from plugins.installed.booking_marketplace import stay_content


def _prop(**kw):
    base = dict(
        name='Test Stay',
        property_type='hotel',
        star_rating=0,
        amenities=[],
        region='',
        location='',
    )
    base.update(kw)
    return SimpleNamespace(**base)


class BestForTests(SimpleTestCase):
    def test_derived_from_type_star_and_amenities(self):
        labels = [
            c['label']
            for c in stay_content.best_for(
                _prop(property_type='boutique', star_rating=5, amenities=['pool', 'family_rooms'])
            )
        ]
        self.assertIn('Design-led stays', labels)  # from property_type
        self.assertIn('A refined stay', labels)  # from star_rating >= 4
        self.assertIn('Sun & swimming', labels)  # from pool
        self.assertIn('Families', labels)  # from family_rooms

    def test_labels_are_deduped(self):
        # villa (type) and kitchenette (amenity) both map to "Self-catering".
        labels = [
            c['label']
            for c in stay_content.best_for(_prop(property_type='villa', amenities=['kitchenette']))
        ]
        self.assertEqual(labels.count('Self-catering'), 1)

    def test_capped(self):
        p = _prop(amenities=list(stay_content._AMENITY_AUDIENCE.keys()))
        self.assertLessEqual(len(stay_content.best_for(p, limit=6)), 6)

    def test_no_signals_is_empty(self):
        self.assertEqual(stay_content.best_for(_prop()), [])

    def test_cards_carry_icon_svg(self):
        self.assertIn('<path', stay_content.best_for(_prop(amenities=['pool']))[0]['icon'])


class LocationIntroTests(SimpleTestCase):
    def test_grounds_in_name_stars_region_and_nearby(self):
        out = stay_content.location_intro(
            _prop(name='Hotel Kotor Bay', star_rating=4, region='kotor', location='Kotor'),
            nearby=[SimpleNamespace(name='Perast'), SimpleNamespace(name='Our Lady of the Rocks')],
        )
        self.assertIn('Hotel Kotor Bay', out)
        self.assertIn('4-star', out)
        self.assertIn('Kotor', out)
        self.assertIn('Bay of Kotor', out)  # real region context
        self.assertIn('Perast', out)  # real nearby place name
        self.assertIn('Our Lady of the Rocks', out)

    def test_two_regions_produce_different_copy(self):
        a = stay_content.location_intro(_prop(name='A', region='budva', location='Budva'))
        b = stay_content.location_intro(_prop(name='B', region='durmitor', location='Zabljak'))
        self.assertNotEqual(a, b)

    def test_safe_with_no_region_or_nearby(self):
        out = stay_content.location_intro(_prop(name='Lone Villa'))
        self.assertIn('Lone Villa', out)
        self.assertTrue(out.endswith('before you book.'))

    def test_accepts_dict_nearby(self):
        out = stay_content.location_intro(
            _prop(name='X', region='tivat'), nearby=[{'name': 'Porto Montenegro'}]
        )
        self.assertIn('Porto Montenegro', out)
