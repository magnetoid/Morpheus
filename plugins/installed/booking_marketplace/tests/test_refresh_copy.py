"""refresh_experience_copy — applies data-module copy to existing rows by slug."""

from django.core.management import call_command
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.management.commands._experiences_data import (
    NEW_EXPERIENCES,
)
from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.catalog.models import Category, Vendor


class RefreshCopyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        v = Vendor.objects.create(name='H', slug='h', is_active=True)
        c = Category.objects.create(name='Adventure', slug='adventure')
        e = NEW_EXPERIENCES[0]
        cls.svc = BookableService.objects.create(
            vendor=v,
            category=c,
            slug=e['slug'],
            name='OLD STALE NAME',
            short_description='old',
            description='old body',
            price=Money(50, 'EUR'),
            listing_kind='experience',
            is_active=True,
        )

    def test_refresh_updates_by_slug_and_is_idempotent(self):
        call_command('refresh_experience_copy', verbosity=0)
        self.svc.refresh_from_db()
        e = NEW_EXPERIENCES[0]
        self.assertEqual(self.svc.name, e['name'])
        self.assertEqual(self.svc.description, e['description'])
        before = (self.svc.name, self.svc.short_description, self.svc.description)
        call_command('refresh_experience_copy', verbosity=0)
        self.svc.refresh_from_db()
        self.assertEqual(before, (self.svc.name, self.svc.short_description, self.svc.description))

    def test_absent_slugs_skipped(self):
        call_command('refresh_experience_copy', verbosity=0)  # only 1 of 125 present — no error
