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

    def test_saving_the_product_updates_the_listing_without_a_call(self):
        p = ensure_product(self.svc)
        p.price = Money(Decimal('70'), 'EUR')
        p.save()
        self.svc.refresh_from_db()
        self.assertEqual(self.svc.price.amount, Decimal('70'))

    def test_a_host_edit_reaches_the_product(self):
        from plugins.installed.booking_marketplace.products import sync_to_product

        p = ensure_product(self.svc)
        self.svc.name = 'Host renamed'
        self.svc.save()
        sync_to_product(self.svc)
        p.refresh_from_db()
        self.assertEqual(p.name, 'Host renamed')

    def test_an_archived_product_stays_archived_when_its_listing_is_saved(self):
        from plugins.installed.booking_marketplace.products import sync_to_product

        p = ensure_product(self.svc)
        p.status = 'archived'
        p.save()
        self.svc.refresh_from_db()
        self.assertFalse(self.svc.is_active)
        sync_to_product(self.svc)
        p.refresh_from_db()
        self.assertEqual(p.status, 'archived')

    def test_a_listing_saved_in_the_editor_gets_its_product(self):
        from plugins.installed.booking_marketplace.forms import ListingForm

        form = ListingForm(
            data={
                'name': 'Sunset sail',
                'slug': 'sunset-sail',
                'listing_kind': 'experience',
                'vendor': self.vendor.pk,
                'duration_minutes': '120',
                'price': '80',
                'is_active': 'on',
                'description': 'Sail',
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        svc = form.save()
        svc.refresh_from_db()
        self.assertIsNotNone(svc.product)
        self.assertEqual(
            (svc.product.name, svc.product.price.amount), ('Sunset sail', Decimal('80'))
        )

    def test_a_renamed_product_slug_still_leads_to_the_booking_page(self):
        # seo's slug watcher rewrites auto_slug redirects to the new product URL, and
        # the product page rendered any service with no redirect: an Add to cart page.
        p = ensure_product(self.svc)
        p.slug = 'kayak-kotor'
        p.save()
        for path in ('/products/kayak-the-bay/', '/products/kayak-kotor/'):
            resp = self.client.get(path)
            self.assertEqual(
                (resp.status_code, resp['Location']), (301, '/bookings/kayak-the-bay/'), path
            )

    def test_graphql_has_no_product_page_for_a_service(self):
        from api.client import internal_graphql

        ensure_product(self.svc)
        data = internal_graphql('query { product(slug: "kayak-the-bay") { slug } }')
        self.assertIsNone((data or {}).get('product'))

    def test_a_bulk_archive_on_products_reaches_the_listing(self):
        # The bulk action used QuerySet.update(), which skips post_save, so
        # PRODUCT_UPDATED never fired and the listing stayed bookable.
        from django.contrib.auth import get_user_model

        p = ensure_product(self.svc)
        self.client.force_login(
            get_user_model().objects.create_superuser('boss@x.io', 'boss@x.io', 'pw')
        )
        self.client.post('/dashboard/products/bulk/', {'action': 'archive', 'ids': [str(p.pk)]})
        self.svc.refresh_from_db()
        p.refresh_from_db()
        self.assertEqual((p.status, self.svc.is_active), ('archived', False))


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
        # Copies under the product's own names; the order shows in primary + alt text.
        self.assertEqual(
            [(primary, alt) for _, primary, alt in rows],
            [(True, 'Kayak the bay'), (False, 'First view'), (False, 'Second view')],
        )
        self.assertTrue(all(default_storage.exists(name) for name, _, _ in rows))

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

    def test_deleting_a_product_photo_keeps_the_listings_file(self):
        # ProductImage deletes its file with its row; a shared file would vanish from
        # the booking page too, and the link backup holds rows, not media.
        self.svc.image.name = self._photo('cover.jpg')
        self.svc.save(update_fields=['image'])
        image = ensure_product(self.svc).images.get()
        self.assertNotEqual(image.image.name, self.svc.image.name)
        image.delete()
        self.assertTrue(default_storage.exists(self.svc.image.name))
