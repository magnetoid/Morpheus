"""apply_listing_content: validated, backed up, written to product, listing and SEO, restorable."""

from __future__ import annotations

import json
import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.management import CommandError, call_command
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.products import ensure_product
from plugins.installed.catalog.models import Category, Product, Vendor

NEW = {
    'kayak-the-bay': {
        'name': 'Sunrise Kayak under the Walls of Kotor',
        'short_description': 'Two calm hours on the water at dawn & no experience needed.',
        'description': '<p>Paddle <strong>under the walls</strong>.</p><h3>Who it suits</h3><p>Beginners.</p>',
        'category': 'water-sports',
        'seo_title': 'Sunrise Kayak Tour in Kotor Bay',
        'seo_description': 'A two-hour sunrise kayak under the walls of Kotor, for beginners.',
        'highlights': ['Calm water at dawn', 'Small group'],
        'itinerary': [{'title': 'Meet at the Sea Gate', 'detail': 'Kit and a briefing.'}],
        'faqs': [{'q': 'Do I need to swim?', 'a': 'A little; you wear a buoyancy vest.'}],
    }
}


class ApplyListingContentTests(TestCase):
    def setUp(self):
        vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        Category.objects.create(name='Water Sports', slug='water-sports')
        self.svc = BookableService.objects.create(
            vendor=vendor,
            name='Kayak the bay',
            slug='kayak-the-bay',
            listing_kind='experience',
            price=Money(Decimal('50'), 'EUR'),
            is_active=True,
            short_description='Paddle the bay.',
            description='Paddle the bay.',
            highlights=['Caves'],
            faqs=[{'q': 'Kids?', 'a': 'From 8.'}],
        )
        self.product = ensure_product(self.svc)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def _run(self, data, *args):
        path = self.dir / 'content.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        out = StringIO()
        call_command('apply_listing_content', str(path), *args, stdout=out)
        return out.getvalue()

    def _meta(self):
        from plugins.installed.seo.models import SeoMeta

        return SeoMeta.objects.filter(
            content_type=ContentType.objects.get_for_model(Product), object_id=str(self.product.pk)
        ).first()

    def test_a_dry_run_writes_nothing(self):
        self.assertIn('would write 1 listing', self._run(NEW, '--dry-run'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Kayak the bay')

    def test_a_real_run_needs_a_backup(self):
        with self.assertRaisesMessage(CommandError, '--backup'):
            self._run(NEW)

    def test_problems_stop_the_run_before_any_write(self):
        bad = {
            'kayak-the-bay': {
                **NEW['kayak-the-bay'],
                'faqs': [{'q': 'Kids?', 'a': ''}],
                'short_description': 'word ' * 80,
            },
            'no-such-listing': {'name': 'Ghost'},
        }
        with self.assertRaises(CommandError) as caught:
            self._run(bad, '--backup', str(self.dir / 'b.json'))
        for fragment in (
            'no-such-listing: no listing with a product',
            'faqs must be',
            'short_description is',
        ):
            self.assertIn(fragment, str(caught.exception))
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Kayak the bay')
        self.assertFalse((self.dir / 'b.json').exists())

    def test_it_writes_the_product_the_listing_and_the_seo_row(self):
        self._run(NEW, '--backup', str(self.dir / 'b.json'))
        self.product.refresh_from_db()
        self.svc.refresh_from_db()
        self.assertEqual(self.product.name, 'Sunrise Kayak under the Walls of Kotor')
        self.assertIn('<strong>under the walls</strong>', self.product.description)
        self.assertEqual(self.product.category.slug, 'water-sports')
        self.assertEqual(self.svc.name, 'Sunrise Kayak under the Walls of Kotor')
        self.assertNotIn('<', self.svc.description)
        self.assertEqual(
            self.svc.short_description,
            'Two calm hours on the water at dawn & no experience needed.',
        )
        self.assertEqual(self.svc.category.slug, 'water-sports')
        self.assertEqual(self.svc.itinerary, NEW['kayak-the-bay']['itinerary'])
        self.assertEqual(self.svc.faqs, NEW['kayak-the-bay']['faqs'])
        meta = self._meta()
        self.assertEqual((meta.title, meta.auto_filled), ('Sunrise Kayak Tour in Kotor Bay', False))
        self.assertEqual(meta.provenance.get('title'), 'ai')
        html = self.client.get('/bookings/kayak-the-bay/').content.decode()
        self.assertIn('<title>Sunrise Kayak Tour in Kotor Bay', html)

    def test_the_backup_puts_everything_back(self):
        old = self._meta()
        before = (getattr(old, 'title', ''), getattr(old, 'auto_filled', True))
        backup = self.dir / 'b.json'
        self._run(NEW, '--backup', str(backup))
        self._run(json.loads(backup.read_text()), '--backup', str(self.dir / 'b2.json'))
        self.product.refresh_from_db()
        self.svc.refresh_from_db()
        self.assertEqual(self.product.name, 'Kayak the bay')
        self.assertEqual(self.product.description, 'Paddle the bay.')
        self.assertIsNone(self.product.category_id)
        self.assertEqual(self.svc.highlights, ['Caves'])
        self.assertEqual(self.svc.itinerary, [])
        self.assertEqual(self.svc.faqs, [{'q': 'Kids?', 'a': 'From 8.'}])
        meta = self._meta()
        self.assertEqual((meta.title, meta.auto_filled), before)
