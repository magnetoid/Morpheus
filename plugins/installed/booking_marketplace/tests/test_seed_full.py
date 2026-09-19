"""seed_experiences_full — volume, idempotency, coverage, renames."""

from django.core.management import call_command
from django.test import TestCase

from plugins.installed.booking_marketplace.models import REGIONS, BookableService


class SeedFullTests(TestCase):
    def test_seeds_100_plus_idempotently(self):
        call_command('seed_experiences_full', verbosity=0)
        n1 = BookableService.objects.filter(listing_kind='experience').count()
        self.assertGreaterEqual(n1, 100)
        call_command('seed_experiences_full', verbosity=0)  # re-run: no dupes
        self.assertEqual(BookableService.objects.filter(listing_kind='experience').count(), n1)

    def test_every_region_and_category_covered(self):
        call_command('seed_experiences_full', verbosity=0)
        qs = BookableService.objects.filter(listing_kind='experience')
        self.assertEqual(
            set(qs.values_list('region', flat=True)) | {''},
            {k for k, _ in REGIONS} | {''},
        )
        self.assertGreaterEqual(qs.exclude(category=None).values('category').distinct().count(), 7)

    def test_renames_applied_by_slug(self):
        call_command('seed_experiences', verbosity=0)  # legacy 20
        call_command('seed_experiences_full', verbosity=0)  # applies RENAMES
        from plugins.installed.booking_marketplace.management.commands._experiences_data import (
            RENAMES,
        )

        for slug, fields in list(RENAMES.items())[:3]:
            svc = BookableService.objects.filter(slug=slug).first()
            if svc:
                self.assertEqual(svc.name, fields['name'])
