"""A book's cover: a PDF, PNG or JPG, dropped on the dashboard's one uploader.

The Book details card had a bare file input that took PDFs only. It now uses the
shared drag-and-drop uploader, takes PNG and JPG too, checks each file before it is
stored (name, size and first bytes must agree; an image must open within a pixel
limit), and the 3D preview draws an image cover as it is.
"""

from __future__ import annotations

import io
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.utils.datastructures import MultiValueDict
from djmoney.money import Money
from PIL import Image

from plugins.installed.book_product import covers
from plugins.installed.book_product.dashboard import save_book_fields
from plugins.installed.book_product.graphql.types import BookProductType
from plugins.installed.book_product.models import BookProduct
from plugins.installed.catalog.models import Product

PDF = b'%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n'


def _image(fmt: str, size=(40, 60)) -> bytes:
    buffer = io.BytesIO()
    Image.new('RGB', size, (200, 30, 30)).save(buffer, format=fmt)
    return buffer.getvalue()


def _upload(name: str, content: bytes) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content)


class CheckUploadTests(TestCase):
    def test_takes_a_pdf_a_png_and_a_jpg(self):
        for upload in (
            _upload('cover.pdf', PDF),
            _upload('cover.png', _image('PNG')),
            _upload('cover.JPG', _image('JPEG')),
            _upload('cover.jpeg', _image('JPEG')),
        ):
            with self.subTest(upload.name):
                self.assertEqual(covers.check_upload(upload), '')
                self.assertEqual(upload.tell(), 0)

    def test_refuses_another_kind_of_file(self):
        self.assertIn('PDF, PNG or JPG', covers.check_upload(_upload('cover.gif', b'GIF89a')))
        self.assertIn('PDF, PNG or JPG', covers.check_upload(_upload('cover', PDF)))

    def test_refuses_a_file_whose_bytes_are_not_what_its_name_says(self):
        self.assertIn('not the kind', covers.check_upload(_upload('cover.pdf', _image('PNG'))))
        self.assertIn('not the kind', covers.check_upload(_upload('cover.png', PDF)))
        self.assertIn('not the kind', covers.check_upload(_upload('cover.jpg', _image('PNG'))))

    def test_refuses_a_broken_image(self):
        broken = _image('PNG')[:40]
        self.assertIn('could not be read', covers.check_upload(_upload('cover.png', broken)))

    def test_refuses_an_image_over_the_pixel_limit(self):
        with mock.patch.object(covers, 'MAX_PIXELS', 40 * 60 - 1):
            self.assertIn('too large', covers.check_upload(_upload('cover.png', _image('PNG'))))

    def test_refuses_a_file_over_the_size_limit(self):
        with mock.patch.object(covers, 'MAX_BYTES', len(PDF) - 1):
            self.assertIn('over', covers.check_upload(_upload('cover.pdf', PDF)))

    def test_cover_type(self):
        for name, kind in (
            ('book_covers/a.PDF', 'pdf'),
            ('book_covers/a.jpg', 'image'),
            ('book_covers/a.png', 'image'),
            ('book_covers/a.gif', ''),
        ):
            with self.subTest(name):
                self.assertEqual(covers.cover_type(SimpleNamespace(name=name)), kind)
        self.assertEqual(covers.cover_type(None), '')


class SaveCoverTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Cover test',
            slug='cover-test',
            sku='COVER-1',
            price=Money(Decimal('5.00'), 'USD'),
        )

    def _request(self):
        request = RequestFactory().post('/dashboard/products/x/')
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def _save(self, upload=None, request=None, **post):
        files = MultiValueDict({'cover_pdf': [upload]}) if upload else MultiValueDict()
        save_book_fields(self.product, {'book_submitted': '1', **post}, files, request=request)
        return BookProduct.objects.get(product=self.product)

    def test_an_image_cover_is_stored(self):
        book = self._save(_upload('front.png', _image('PNG')))

        self.assertTrue(book.cover_pdf.name.endswith('.png'))
        self.assertEqual(book.cover_type, 'image')

    def test_a_refused_file_keeps_the_cover_and_says_why(self):
        book = self._save(_upload('front.pdf', PDF))
        request = self._request()

        book = self._save(_upload('front.png', PDF), request=request)

        self.assertTrue(book.cover_pdf.name.endswith('.pdf'))
        self.assertEqual(
            [str(m) for m in get_messages(request)],
            ['The cover was not saved: front.png is not the kind of file its name says.'],
        )

    def test_the_uploaders_clear_box_removes_the_cover(self):
        self._save(_upload('front.pdf', PDF))

        book = self._save(**{'cover_pdf-clear': 'on'})

        self.assertFalse(book.cover_pdf)
        self.assertEqual(book.cover_type, '')

    def test_a_save_without_a_file_keeps_the_cover(self):
        self._save(_upload('front.jpg', _image('JPEG')))

        self.assertTrue(self._save(author='Someone').cover_pdf.name.endswith('.jpg'))

    def test_graphql_names_the_kind(self):
        book = self._save(_upload('front.jpg', _image('JPEG')))

        typed = BookProductType.from_model(book)

        self.assertEqual(typed.cover_type, 'image')
        self.assertTrue(typed.cover_pdf_url.endswith('.jpg'))


class CoverCardTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='coverstaff', email='coverstaff@example.com', password='x', is_staff=True
        )
        self.client.force_login(user)
        self.product = Product.objects.create(
            name='Cover card',
            slug='cover-card',
            sku='COVER-2',
            price=Money(Decimal('5.00'), 'USD'),
        )

    def _page(self) -> str:
        response = self.client.get(f'/dashboard/products/{self.product.pk}/')
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def _uploader(self, body: str) -> str:
        start = body.index('name="cover_pdf"')
        return body[body.rindex('data-media-uploader', 0, start) : body.index('</p>', start)]

    def test_the_card_has_the_drag_and_drop_uploader_for_pdf_png_and_jpg(self):
        uploader = self._uploader(self._page())

        self.assertIn('data-mode="field"', uploader)
        self.assertIn(f'accept="{covers.ACCEPT}"', uploader)
        self.assertIn('data-max-mb="50"', uploader)
        self.assertIn('name="cover_pdf-clear"', uploader)
        self.assertIn('Add cover', uploader)
        self.assertNotIn('class="input"', uploader)

    def test_a_pdf_cover_shows_as_a_named_file_and_its_3d_preview(self):
        book = BookProduct.objects.create(product=self.product)
        book.cover_pdf.save('front.pdf', _upload('front.pdf', PDF))

        body = self._page()
        uploader = self._uploader(body)

        self.assertIn('Replace cover', uploader)
        self.assertRegex(uploader, r'data-field-doc href="[^"]+front[^"]*\.pdf"')
        self.assertIn('data-cover-type="pdf"', body)

    def test_an_image_cover_previews_as_a_picture_and_in_3d(self):
        book = BookProduct.objects.create(product=self.product)
        book.cover_pdf.save('front.png', _upload('front.png', _image('PNG')))

        body = self._page()
        uploader = self._uploader(body)

        self.assertRegex(uploader, r'data-field-preview src="[^"]+front[^"]*\.png"')
        self.assertRegex(body, r'data-cover-url="[^"]+\.png" data-cover-type="image"')
