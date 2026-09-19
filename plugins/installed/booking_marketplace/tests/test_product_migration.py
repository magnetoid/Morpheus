"""migrate_products_to_bookable — copies catalog.Product into product-kind services."""

from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService


def _product(**kw):
    from plugins.installed.catalog.models import Category, Product, Vendor
    v = kw.pop('vendor', None)
    cat = Category.objects.create(name='Wine', slug='wine')
    return Product.objects.create(
        name=kw.get('name', 'Vranac Reserve'),
        slug=kw.get('slug', 'vranac-reserve'),
        sku=kw.get('sku', 'SKU-VR'),
        price=Money(Decimal('18.00'), 'EUR'),
        short_description='Bold red', description='A barrel-aged Vranac.',
        category=cat, status='active', vendor=v,
    )


class MigrationTests(TestCase):
    def test_product_becomes_product_kind_service(self):
        p = _product()
        call_command('migrate_products_to_bookable')
        svc = BookableService.objects.get(slug='vranac-reserve')
        self.assertEqual(svc.listing_kind, 'product')
        self.assertEqual(svc.name, 'Vranac Reserve')
        self.assertEqual(svc.price, Money(18, 'EUR'))
        self.assertEqual(svc.category.slug, 'wine')

    def test_source_product_archived(self):
        p = _product()
        call_command('migrate_products_to_bookable')
        p.refresh_from_db()
        self.assertEqual(p.status, 'archived')

    def test_idempotent_rerun(self):
        _product()
        call_command('migrate_products_to_bookable')
        call_command('migrate_products_to_bookable')
        self.assertEqual(
            BookableService.objects.filter(slug='vranac-reserve').count(), 1
        )

    def test_fallback_vendor_created_when_product_has_none(self):
        _product(vendor=None)
        call_command('migrate_products_to_bookable')
        svc = BookableService.objects.get(slug='vranac-reserve')
        self.assertEqual(svc.vendor.slug, 'montenegro-makers')
