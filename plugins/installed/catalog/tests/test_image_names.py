"""A product photo is stored under the product's title, and a stored one never moves.

Owner's ask (2026-10-10): for image search, a picture uploaded to a product takes
the product's title as its file name ("wind-up-emergency-radio.jpg", not
"IMG_4821.JPG"), and no existing link may break. Only a NEW file is named;
Django never renames a stored file, so every URL already published keeps
working. The alt text a dashboard upload leaves empty becomes the title too.
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
        self.assertEqual(self._upload().image.name, 'products/wind-up-emergency-radio.jpg')

    def test_more_photos_of_one_product_count_up(self):
        self._upload()
        self.assertEqual(
            self._upload('photo.png').image.name, 'products/wind-up-emergency-radio-2.png'
        )

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
        self.assertEqual(self._upload('a.webp').image.name, 'products/wind-up-radio.webp')

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
        self.assertEqual(image.image.name, 'products/wind-up-emergency-radio.png')
