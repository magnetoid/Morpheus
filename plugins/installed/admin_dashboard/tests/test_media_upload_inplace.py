"""A photo dropped on the product gallery is saved and shown without a reload.

Owner's ask (2026-10-10): dropping an image made the page blink, because the
uploader reloaded the whole page to draw the new tile, which also threw away
anything typed elsewhere on the form. The upload now answers the uploader with
the tile itself, rendered by the same include the page uses, and queues no
flash message (it would pop up on some later page instead).
"""

from __future__ import annotations

import io
import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from djmoney.money import Money


def _png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new('RGB', (24, 24), (30, 90, 60)).save(buf, 'PNG')
    return buf.getvalue()


class GalleryUploadInPlaceTests(TestCase):
    def setUp(self):
        media = tempfile.mkdtemp(prefix='morph-upload-inplace-')
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)
        from plugins.installed.catalog.models import Product

        self.product = Product.objects.create(
            name='Folding Solar Panel',
            slug='folding-solar-panel',
            sku='SOLAR-1',
            price=Money(Decimal('89.00'), 'USD'),
            status='active',
        )
        staff = get_user_model().objects.create_user(
            username='gallery-staff', email='gallery@x.test', password='x', is_staff=True,
            is_superuser=True,
        )  # fmt: skip
        self.client = Client()
        self.client.force_login(staff)
        self.url = f'/dashboard/products/{self.product.pk}/images/upload/'

    def _upload(self, *, ajax: bool):
        extra = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'} if ajax else {}
        return self.client.post(
            self.url,
            {'image': SimpleUploadedFile('IMG_1.png', _png(), content_type='image/png')},
            **extra,
        )

    def test_a_fetch_upload_answers_with_the_tile(self):
        from plugins.installed.catalog.models import ProductImage

        response = self._upload(ajax=True)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        image = ProductImage.objects.get(product=self.product)
        self.assertTrue(data['ok'])
        self.assertIn(f'data-id="{image.id}"', data['html'])
        self.assertIn('data-kind="image"', data['html'])
        self.assertIn('Slot 1', data['html'])
        self.assertIn('is-cover', data['html'])  # the first photo is the cover

    def test_a_fetch_upload_leaves_no_message_for_a_later_page(self):
        self._upload(ajax=True)
        page = self.client.get(f'/dashboard/products/{self.product.pk}/')
        self.assertNotContains(page, 'Image uploaded.')

    def test_a_plain_form_post_still_redirects_with_its_message(self):
        response = self._upload(ajax=False)
        self.assertEqual(response.status_code, 302)
        page = self.client.get(response['Location'])
        self.assertContains(page, 'Image uploaded.')

    def test_the_page_draws_its_tiles_with_the_same_include(self):
        self._upload(ajax=True)
        page = self.client.get(f'/dashboard/products/{self.product.pk}/').content.decode()
        self.assertIn('data-media-count', page)
        self.assertIn('muploader-tile__cover-pill', page)
