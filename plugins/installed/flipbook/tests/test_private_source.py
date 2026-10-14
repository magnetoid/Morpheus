"""A paid PDF is never downloadable from its public path.

Live on dotbooks (2026-10-12): the flipbook preview printed the product's full
PDF address (`/media/digital/<name>.pdf`) into its page, and /media/ served it
to anyone, with no sign-in; 510 digital products sat under that path. A buyer
gets the file through a download token, which reads it from disk. Now
/media/digital/ answers only staff, and the preview loads a PDF of its first
pages made on the server.
"""

from __future__ import annotations

import io
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from djmoney.money import Money
from pypdf import PdfReader, PdfWriter

from plugins.installed.catalog.models import Product


def _pdf(pages: int) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=300)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class PrivateDigitalFileTests(TestCase):
    def setUp(self):
        # A real file: /media/ is served from disk, from the MEDIA_ROOT the urlconf bound
        # at import (morph/urls.py), so the file goes there and the cleanup deletes it.
        override = override_settings(
            STORAGES={
                **settings.STORAGES,
                'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            },
        )
        override.enable()
        self.addCleanup(override.disable)
        self.product = Product.objects.create(
            name='Paid Book',
            slug='paid-book-flip',
            sku='PAID-FLIP',
            price=Money(Decimal('8.00'), 'USD'),
            product_type='digital',
            status='active',
        )
        self.product.digital_file.save('paid-book-flip-test.pdf', ContentFile(_pdf(5)), save=True)
        self.addCleanup(self.product.digital_file.delete, save=False)
        self.path = '/media/' + self.product.digital_file.name

    def test_the_file_is_not_public(self):
        self.assertEqual(self.client.get(self.path).status_code, 404)

    def test_staff_can_still_open_it(self):
        staff = get_user_model().objects.create_user(
            username='flip-staff', email='fs@x.io', password='pw', is_staff=True
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.path).status_code, 200)

    def test_the_preview_page_does_not_name_the_file(self):
        body = self.client.get('/p/paid-book-flip/flipbook/').content.decode()
        self.assertNotIn(self.product.digital_file.name, body)
        self.assertIn('/flipbook/preview.pdf', body)

    def test_the_preview_holds_only_the_first_pages(self):
        with mock.patch(
            'plugins.installed.flipbook.views._plugin_config',
            return_value={'max_preview_pages': 2},
        ):
            resp = self.client.get('/p/paid-book-flip/flipbook/preview.pdf')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertEqual(len(PdfReader(io.BytesIO(resp.content)).pages), 2)
