"""Derived nav/home content — every surfaced category resolves to real services."""

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService, ServiceReview
from plugins.installed.booking_marketplace.services import active_categories
from plugins.installed.booking_marketplace.templatetags.booking_tags import (
    featured_filters,
    hero_pills,
    home_categories,
    home_testimonials,
)
from plugins.installed.catalog.models import Category, Vendor


def _mk(slug, cat, vendor):
    return BookableService.objects.create(
        vendor=vendor,
        name=slug,
        slug=slug,
        category=cat,
        price=Money(50, 'EUR'),
        listing_kind='experience',
        is_active=True,
    )


class DerivedCategoriesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vendor = Vendor.objects.create(name='Host', slug='host', is_active=True)
        cls.adv = Category.objects.create(name='Adventure', slug='adventure')
        cls.wine = Category.objects.create(name='Wine', slug='wine')
        Category.objects.create(name='Empty', slug='empty')  # no services → hidden
        _mk('rafting', cls.adv, cls.vendor)
        _mk('hike', cls.adv, cls.vendor)
        _mk('tasting', cls.wine, cls.vendor)

    def test_only_categories_with_active_services(self):
        names = [c['name'] for c in active_categories()]
        self.assertEqual(names, ['Adventure', 'Wine'])  # count desc; Empty hidden

    def test_counts(self):
        by_name = {c['name']: c['count'] for c in active_categories()}
        self.assertEqual(by_name, {'Adventure': 2, 'Wine': 1})

    def test_hero_pills_derive(self):
        self.assertEqual(hero_pills(), ['Adventure', 'Wine'])

    def test_featured_filters_derive(self):
        self.assertEqual(featured_filters(), ['Adventure', 'Wine'])

    def test_home_categories_have_links_and_icons(self):
        cats = home_categories()
        self.assertEqual(cats[0]['label'], 'Adventure')
        self.assertIn('/bookings/?category=Adventure', cats[0]['href'])
        self.assertIn('<svg', cats[0]['icon'])  # default glyph acceptable

    def test_inactive_service_drops_category(self):
        BookableService.objects.filter(category=self.wine).update(is_active=False)
        self.assertEqual([c['name'] for c in active_categories()], ['Adventure'])

    def test_disabled_category_hidden_even_with_services(self):
        Category.objects.filter(name='Wine').update(is_active=False)
        self.assertEqual([c['name'] for c in active_categories()], ['Adventure'])


class DerivedTestimonialsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        vendor = Vendor.objects.create(name='Host', slug='host', is_active=True)
        cat = Category.objects.create(name='Adventure', slug='adventure')
        svc = _mk('rafting', cat, vendor)
        ServiceReview.objects.create(
            service=svc,
            author_name='Ana',
            rating=5,
            body='Unforgettable rapids.',
            title='Wow',
        )
        ServiceReview.objects.create(service=svc, author_name='Lo', rating=3, body='meh')

    def test_only_high_rated_with_text(self):
        t = home_testimonials()
        self.assertEqual(len(t), 1)
        self.assertEqual(t[0]['name'], 'Ana')
        self.assertEqual(t[0]['avatar'], 'A')
        self.assertEqual(t[0]['text'], 'Unforgettable rapids.')
        self.assertEqual(t[0]['experience'], 'rafting')

    def test_empty_reviews_empty_list(self):
        ServiceReview.objects.all().delete()
        self.assertEqual(home_testimonials(), [])
