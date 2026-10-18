"""A product photo is stored under the product's title, and a stored one never moves.

Owner's ask (2026-10-10): for image search, a picture uploaded to a product takes
the product's title as its file name ("wind-up-emergency-radio-3f9a2c.jpg", not
"IMG_4821.JPG"), and no existing link may break. Only a NEW file is named;
Django never renames a stored file, so every URL already published keeps
working. The alt text a dashboard upload leaves empty becomes the title too.

A name is used once. A photo uploaded after another was deleted used to take the
deleted photo's name, and everything that remembers an address showed the
deleted photo instead: the dashboard page, browsers (31 days), Cloudflare and the
resized copies under /img/ (a year). The owner saw old pictures come back in the
uploader; Supernatural and Irving were serving them (2026-10-18).
"""

from __future__ import annotations

import io
import shutil
import tempfile
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from djmoney.money import Money


def _png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new('RGB', (32, 32), (120, 80, 40)).save(buf, 'PNG')
    return buf.getvalue()


class ProductImageNameTests(TestCase):
    def setUp(self):
        media = tempfile.mkdtemp(prefix='morph-img-names-')
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        # Real files: the names come from what the storage finds on disk.
        override = override_settings(
            MEDIA_ROOT=media,
            STORAGES={
                **settings.STORAGES,
                'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            },
        )
        override.enable()
        self.addCleanup(override.disable)
        from plugins.installed.catalog.models import Product

        self.product = Product.objects.create(
            name='Wind-Up Emergency Radio',
            slug='wind-up-radio',
            sku='RADIO-1',
            price=Money(Decimal('29.00'), 'USD'),
            status='active',
        )

    def _upload(self, filename: str = 'IMG_4821.JPG'):
        from plugins.installed.catalog.models import ProductImage

        image = ProductImage(product=self.product, alt_text='x')
        image.image.save(filename, ContentFile(_png()), save=True)
        return image

    def test_a_new_photo_is_named_after_the_product(self):
        self.assertRegex(
            self._upload().image.name, r'^products/wind-up-emergency-radio-[0-9a-f]{6}\.jpg$'
        )

    def test_more_photos_of_one_product_get_names_of_their_own(self):
        first = self._upload().image.name
        second = self._upload('photo.png').image.name
        self.assertRegex(second, r'^products/wind-up-emergency-radio-[0-9a-f]{6}\.png$')
        self.assertNotEqual(first.rsplit('.', 1)[0], second.rsplit('.', 1)[0])

    def test_a_new_photo_never_takes_a_deleted_photos_name(self):
        first = self._upload()
        name = first.image.name
        first.delete()
        self.assertNotEqual(self._upload().image.name, name)

    def test_a_long_title_keeps_the_random_part_and_fits_the_column(self):
        self.product.name = 'Radio ' * 40
        self.product.save()
        name = self._upload('photo.jpeg').image.name
        self.assertRegex(name, r'^products/radio-[a-z-]+-[0-9a-f]{6}\.jpeg$')
        self.assertLessEqual(len(name), 100)
        self.assertLessEqual(len(f'products/webp/{name[9:].rsplit(".", 1)[0]}.avif'), 100)

    def test_a_stored_photo_keeps_its_name_whatever_happens(self):
        from plugins.installed.catalog.models import ProductImage

        stored = ProductImage.objects.create(
            product=self.product, image='products/IMG_0001.jpg', alt_text='old'
        )
        self.product.name = 'Hand-Crank Radio'
        self.product.save()
        stored.alt_text = 'new alt'
        stored.save()
        stored.refresh_from_db()
        self.assertEqual(stored.image.name, 'products/IMG_0001.jpg')

    def test_a_title_with_no_usable_letters_falls_back_to_the_slug(self):
        self.product.name = '★★★'
        self.product.save()
        self.assertRegex(
            self._upload('a.webp').image.name, r'^products/wind-up-radio-[0-9a-f]{6}\.webp$'
        )

    def test_a_dashboard_upload_without_alt_text_takes_the_title(self):
        from plugins.installed.catalog.models import ProductImage

        staff = get_user_model().objects.create_user(
            username='img-staff', email='img@x.test', password='x', is_staff=True,
            is_superuser=True,
        )  # fmt: skip
        client = Client()
        client.force_login(staff)
        client.post(
            f'/dashboard/products/{self.product.pk}/images/upload/',
            {'image': SimpleUploadedFile('IMG_9.png', _png(), content_type='image/png')},
        )
        image = ProductImage.objects.get(product=self.product)
        self.assertEqual(image.alt_text, 'Wind-Up Emergency Radio')
        self.assertRegex(image.image.name, r'^products/wind-up-emergency-radio-[0-9a-f]{6}\.png$')

    def test_the_uploader_never_shows_a_deleted_photos_address_for_a_new_one(self):
        # The owner's report: delete a photo, upload another, and the new tile showed
        # the old picture, because it pointed at the old picture's address.
        staff = get_user_model().objects.create_user(
            username='img-staff2', email='img2@x.test', password='x', is_staff=True,
            is_superuser=True,
        )  # fmt: skip
        client = Client()
        client.force_login(staff)
        base = f'/dashboard/products/{self.product.pk}/images'

        def upload():
            return client.post(
                f'{base}/upload/',
                {'image': SimpleUploadedFile('IMG_9.png', _png(), content_type='image/png')},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            ).json()

        first = upload()
        client.post(f'{base}/{first["id"]}/delete/')
        second = upload()
        self.assertTrue(first['url'] and second['url'])
        self.assertNotEqual(second['url'], first['url'])
        self.assertNotIn(first['url'], second['html'])
