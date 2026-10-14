"""link_listing_products: link every listing to its catalog Product, with a backup first."""

from __future__ import annotations

import json
import shutil
import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.catalog.models import Product, Vendor


class LinkListingProductsTests(TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.backup = Path(tmp) / 'b.json'
        vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        for name, slug, kind in (
            ('Kayak the bay', 'kayak-the-bay', 'experience'),
            ('Vranac', 'vranac', 'product'),
        ):
            BookableService.objects.create(
                vendor=vendor,
                name=name,
                slug=slug,
                listing_kind=kind,
                price=Money(Decimal('20'), 'EUR'),
                is_active=True,
            )
        self.old = Product.objects.create(
            name='Vranac',
            slug='vranac',
            sku='OLD',
            status='archived',
            price=Money(Decimal('1'), 'EUR'),
        )

    def _run(self):
        out = StringIO()
        call_command('link_listing_products', backup=str(self.backup), stdout=out)
        return out.getvalue()

    def test_links_every_listing_reusing_the_archived_copy_after_a_backup(self):
        out = self._run()
        self.assertIn('linked=2 reused=1 created=1', out)
        self.assertEqual(BookableService.objects.filter(product__isnull=True).count(), 0)
        self.old.refresh_from_db()
        self.assertEqual((self.old.product_type, self.old.status), ('service', 'active'))
        dump = json.loads(self.backup.read_text())
        self.assertEqual(
            {row['fields']['slug'] for row in dump['listings']}, {'kayak-the-bay', 'vranac'}
        )
        archived = [row for row in dump['products'] if row['pk'] == str(self.old.pk)]
        self.assertEqual(archived[0]['fields']['status'], 'archived')  # the state before the run

    def test_a_second_run_changes_nothing(self):
        self._run()
        count = Product.objects.count()
        self.assertIn('linked=0 reused=0 created=0', self._run())
        self.assertEqual(Product.objects.count(), count)

    def test_it_refuses_to_run_without_a_writable_backup(self):
        with self.assertRaises(CommandError):
            call_command(
                'link_listing_products', backup='/nonexistent-dir/b.json', stdout=StringIO()
            )
        self.assertEqual(BookableService.objects.filter(product__isnull=False).count(), 0)

    def test_a_dry_run_lists_what_it_would_do_and_changes_nothing(self):
        out = StringIO()
        call_command('link_listing_products', dry_run=True, stdout=out)
        text = out.getvalue()
        self.assertIn('reuse vranac (archived)', text)
        self.assertIn('create kayak-the-bay', text)
        self.assertIn('would link 2: reuse 1, create 1', text)
        self.assertEqual(BookableService.objects.filter(product__isnull=False).count(), 0)
        self.assertFalse(self.backup.exists())

    def test_a_real_run_needs_a_backup_path(self):
        with self.assertRaises(CommandError):
            call_command('link_listing_products', stdout=StringIO())
