"""The SEO card's share preview shows the image the store will actually share.

With no share image of its own, a product page shares its cover
(`storefront/views/catalog.py` passes the primary image as `seo_image`), but
the panel's preview looked only at its own "Share image" box and a host-form
input the product form does not have. So a merchant who added photos still saw
"No share image" — on supernatural and Irving, every product (2026-10-16).

Two halves: the page renders the current cover into the panel, and the gallery
uploader announces a new cover (upload, reorder, delete) without a reload, which
the panel listens for. The event name is the contract between two apps' files,
so it is checked on both sides.
"""

from __future__ import annotations

import io
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from plugins.installed.catalog.models import Product, ProductImage

_MEDIA = tempfile.mkdtemp(prefix='seo-cover-preview-')
EVENT = 'morph:media-cover'


def _png(name='cover.png') -> SimpleUploadedFile:
    from PIL import Image

    buf = io.BytesIO()
    Image.new('RGB', (32, 32), (90, 120, 200)).save(buf, 'PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=_MEDIA)
class CoverPreviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            username='seo-cover-staff',
            email='cover@example.test',
            password='pw',
            is_staff=True,
            is_superuser=True,
        )
        cls.product = Product.objects.create(
            name='Cover Probe', slug='cover-probe', sku='CVP-1', price=Decimal('9.00')
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    def setUp(self):
        self.client.force_login(self.staff)

    def _form(self):
        resp = self.client.get(
            reverse('admin_dashboard:product_edit', kwargs={'product_id': self.product.id})
        )
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def test_the_panel_carries_the_products_cover(self):
        image = ProductImage.objects.create(
            product=self.product, image=_png(), is_primary=True, sort_order=0
        )
        self.assertIn(f'data-cover-image="{image.image.url}"', self._form())

    def test_a_product_without_photos_has_an_empty_cover(self):
        self.assertIn('data-cover-image=""', self._form())

    def test_the_uploader_announces_the_cover_and_the_panel_listens(self):
        js = Path(
            settings.BASE_DIR,
            'plugins/installed/admin_dashboard/static/admin_dashboard/media-uploader.js',
        )
        self.assertIn(f"'{EVENT}'", js.read_text())
        self.assertIn(f"'{EVENT}'", self._form())
