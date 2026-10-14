"""A marketplace listing extends a catalog Product (docs/plans/booking-extends-product-2026-10.md).

Product owns name, slug, descriptions, price, category, host, photos and status; the
listing keeps the booking data. Montenegro's 142 listings were invisible to the
dashboard's Products, Linda's product tools and web stories because they lived only
in their own table.
"""

from __future__ import annotations

import shutil
import tempfile
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.products import ensure_product, sync_from_product
from plugins.installed.catalog.models import Product, Vendor


class ListingProductTests(TestCase):
    def setUp(self):
        self.vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        self.svc = BookableService.objects.create(
            vendor=self.vendor,
            name='Kayak the bay',
            slug='kayak-the-bay',
            listing_kind='experience',
            short_description='Paddle',
            description='Long text',
            price=Money(Decimal('50'), 'EUR'),
            original_price=Money(Decimal('60'), 'EUR'),
            is_active=True,
        )

    def test_a_listing_gets_one_service_product_with_its_fields(self):
        p = ensure_product(self.svc)
        self.assertEqual(
            (p.slug, p.name, p.product_type, p.status),
            ('kayak-the-bay', 'Kayak the bay', 'service', 'active'),
        )
        self.assertEqual(p.price.amount, Decimal('50'))
        self.assertEqual(str(p.price.currency), 'EUR')
        self.assertEqual(p.compare_at_price.amount, Decimal('60'))
        self.assertFalse(p.requires_shipping)
        self.assertEqual(ensure_product(self.svc).pk, p.pk)  # idempotent
        self.assertEqual(Product.objects.count(), 1)

    def test_an_archived_good_with_the_same_slug_and_name_is_reused(self):
        old = Product.objects.create(
            name='Kayak the bay',
            slug='kayak-the-bay',
            sku='OLD',
            status='archived',
            price=Money(Decimal('1'), 'EUR'),
        )
        p = ensure_product(self.svc)
        self.assertEqual(p.pk, old.pk)
        self.assertEqual((p.status, p.product_type), ('active', 'service'))

    def test_a_different_product_on_the_slug_is_left_alone(self):
        book = Product.objects.create(
            name='A book',
            slug='kayak-the-bay',
            sku='BOOK',
            status='active',
            price=Money(Decimal('9'), 'EUR'),
        )
        p = ensure_product(self.svc)
        self.assertEqual(p.slug, 'kayak-the-bay-experience')
        book.refresh_from_db()
        self.assertEqual((book.name, book.product_type), ('A book', 'simple'))

    def test_product_edits_flow_to_the_listing(self):
        p = ensure_product(self.svc)
        p.name = 'Kayak the Bay of Kotor'
        p.price = Money(Decimal('55'), 'EUR')
        p.save()
        sync_from_product(p)
        self.svc.refresh_from_db()
        self.assertEqual(
            (self.svc.name, self.svc.price.amount), ('Kayak the Bay of Kotor', Decimal('55'))
        )

    def test_the_product_page_redirects_to_the_booking_page(self):
        ensure_product(self.svc)
        resp = self.client.get('/products/kayak-the-bay/')
        self.assertEqual(resp.status_code, 301)
        self.assertTrue(resp['Location'].endswith('/bookings/kayak-the-bay/'))


class ListingProductPhotoAndSlugTests(TestCase):
    def setUp(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)
        self.vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        self.svc = BookableService.objects.create(
            vendor=self.vendor,
            name='Kayak the bay',
            slug='kayak-the-bay',
            listing_kind='experience',
            price=Money(Decimal('50'), 'EUR'),
            is_active=True,
        )

    def _photo(self, name):
        from io import BytesIO

        from PIL import Image

        buf = BytesIO()
        Image.new('RGB', (4, 4), 'teal').save(buf, 'JPEG')
        return default_storage.save(f'experiences/{name}', ContentFile(buf.getvalue()))

    def test_the_listing_photos_become_the_product_images_in_order(self):
        from plugins.installed.booking_marketplace.models import ServiceImage

        self.svc.image.name = self._photo('cover.jpg')
        self.svc.save(update_fields=['image'])
        ServiceImage.objects.create(
            service=self.svc, image=self._photo('second.jpg'), alt='Second view', sort_order=2
        )
        ServiceImage.objects.create(
            service=self.svc, image=self._photo('first.jpg'), alt='First view', sort_order=1
        )
        ServiceImage.objects.create(
            service=self.svc, image='experiences/gallery/gone.jpg', sort_order=3
        )
        p = ensure_product(self.svc)
        rows = list(p.images.order_by('sort_order').values_list('image', 'is_primary', 'alt_text'))
        self.assertEqual(
            [(name.rsplit('/', 1)[1][:5], primary, alt) for name, primary, alt in rows],
            [
                ('cover', True, 'Kayak the bay'),
                ('first', False, 'First view'),
                ('secon', False, 'Second view'),
            ],
        )

    def test_a_reused_product_keeps_its_own_photos(self):
        from plugins.installed.catalog.models import ProductImage

        old = Product.objects.create(
            name='Kayak the bay',
            slug='kayak-the-bay',
            sku='OLD',
            status='archived',
            price=Money(Decimal('1'), 'EUR'),
        )
        ProductImage.objects.create(product=old, image=self._photo('old.jpg'), is_primary=True)
        self.svc.image.name = self._photo('cover.jpg')
        self.svc.save(update_fields=['image'])
        self.assertEqual(ensure_product(self.svc).images.count(), 1)

    def test_an_unrelated_product_on_the_fallback_slug_is_left_alone(self):
        Product.objects.create(
            name='A book', slug='kayak-the-bay', sku='BOOK', price=Money(Decimal('9'), 'EUR')
        )
        Product.objects.create(
            name='A map',
            slug='kayak-the-bay-experience',
            sku='MAP',
            price=Money(Decimal('4'), 'EUR'),
        )
        p = ensure_product(self.svc)
        self.assertEqual(p.slug, 'kayak-the-bay-experience-2')
        self.assertEqual(Product.objects.get(sku='MAP').name, 'A map')
