"""The customer's library and the order pages' downloads (library.py).

A digital line is delivered when its order is paid, placed to be paid later (cash
on delivery, bank transfer) or fulfilled, and never waits for a shipment. The
file is the buyer's alone, and an audiobook delivers its narration.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.template import Context, Template
from django.test import TestCase, override_settings
from djmoney.money import Money

MEDIA = tempfile.mkdtemp()


def _user(email):
    return get_user_model().objects.create_user(username=email, email=email, password='pw-1234!')


@override_settings(MEDIA_ROOT=MEDIA)
class LibraryTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, MEDIA, ignore_errors=True)

    def setUp(self):
        from plugins.installed.catalog.models import Product

        self.buyer = _user('buyer@example.com')
        self.ebook = Product.objects.create(
            name='The Long Road',
            slug='long-road',
            sku='LR-1',
            status='active',
            product_type='digital',
            requires_shipping=False,
            price=Money(Decimal('8.00'), 'USD'),
        )
        self.ebook.digital_file.save('long-road.pdf', ContentFile(b'%PDF-1.4 book'), save=True)
        self.mug = Product.objects.create(
            name='Mug',
            slug='mug',
            sku='MUG-1',
            status='active',
            price=Money(Decimal('5.00'), 'USD'),
        )

    def _order(self, *, product=None, customer='buyer', variant=None, **fields):
        from plugins.installed.orders.models import Order, OrderItem

        fields.setdefault('payment_gateway', 'stripe')
        order = Order.objects.create(
            email='buyer@example.com',
            customer=self.buyer if customer == 'buyer' else customer,
            subtotal=Money(8, 'USD'),
            total=Money(8, 'USD'),
            **fields,
        )
        product = product or self.ebook
        line = OrderItem.objects.create(
            order=order,
            product=product,
            variant=variant,
            product_name=product.name,
            sku=product.sku,
            quantity=1,
            unit_price=Money(8, 'USD'),
            total_price=Money(8, 'USD'),
        )
        return order, line


class DeliveryRuleTests(LibraryTestCase):
    def test_states(self):
        from plugins.installed.digital_products.library import library

        self._order(payment_status='paid', status='processing')
        self._order(payment_status='unpaid', status='pending')  # card not through yet
        self._order(payment_status='unpaid', status='pending', payment_gateway='cod')
        self._order(payment_status='unpaid', status='shipped')
        self._order(payment_status='unpaid', status='cancelled', payment_gateway='cod')
        states = sorted(item.state for item in library(self.buyer))
        self.assertEqual(states, ['ready', 'ready', 'ready', 'waiting'])

    def test_goods_are_not_in_the_library(self):
        from plugins.installed.digital_products.library import library

        self._order(product=self.mug, payment_status='paid')
        self.assertEqual(library(self.buyer), [])

    def test_order_paid_later_issues_its_links_when_placed(self):
        from morpheus.core import MorpheusEvents, hook_registry
        from plugins.installed.digital_products.models import DownloadToken

        cod, _ = self._order(payment_status='unpaid', status='pending', payment_gateway='cod')
        card, _ = self._order(payment_status='unpaid', status='pending')
        with self.captureOnCommitCallbacks(execute=True):
            hook_registry.fire(MorpheusEvents.ORDER_PLACED, order=cod)
            hook_registry.fire(MorpheusEvents.ORDER_PLACED, order=card)
        self.assertEqual(DownloadToken.objects.filter(order=cod).count(), 1)
        self.assertFalse(DownloadToken.objects.filter(order=card).exists())


class LibraryPageTests(LibraryTestCase):
    def test_page_lists_the_purchase_with_its_download(self):
        _, line = self._order(payment_status='unpaid', status='pending', payment_gateway='cod')
        self.client.force_login(self.buyer)
        body = self.client.get('/account/downloads/').content.decode()
        self.assertIn('The Long Road', body)
        self.assertIn(f'/account/library/{line.pk}/file/', body)

    def test_file_is_the_buyers_alone(self):
        _, line = self._order(payment_status='paid', status='processing')
        url = f'/account/library/{line.pk}/file/'
        self.client.force_login(_user('someone@example.com'))
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.buyer)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'%PDF-1.4 book')
        self.assertIn('private', response['Cache-Control'])

    def test_waiting_line_has_no_file(self):
        _, line = self._order(payment_status='unpaid', status='pending')
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(f'/account/library/{line.pk}/file/').status_code, 404)

    def test_player_gets_byte_ranges(self):
        _, line = self._order(payment_status='paid', status='processing')
        self.client.force_login(self.buyer)
        url = f'/account/library/{line.pk}/file/?play=1'
        part = self.client.get(url, HTTP_RANGE='bytes=0-3')
        self.assertEqual(part.status_code, 206)
        self.assertEqual(b''.join(part.streaming_content), b'%PDF')
        self.assertEqual(part['Content-Range'], 'bytes 0-3/13')
        self.assertEqual(self.client.get(url, HTTP_RANGE='bytes=99-').status_code, 416)


class OrderPageDeliveryTests(LibraryTestCase):
    def _render(self, line):
        return Template(
            '{% load morph %}{% order_line_delivery line as d %}'
            '{% if d %}{{ d.state }}|{{ d.file_url }}{% else %}none{% endif %}'
        ).render(Context({'line': line}))

    def test_digital_line_answers_goods_do_not(self):
        _, ebook = self._order(payment_status='paid', status='processing')
        _, mug = self._order(product=self.mug, payment_status='paid', status='processing')
        self.assertEqual(self._render(ebook), f'ready|/account/library/{ebook.pk}/file/')
        self.assertEqual(self._render(mug), 'none')

    def test_guest_gets_the_emailed_link(self):
        from plugins.installed.digital_products.app import DigitalProductsPlugin
        from plugins.installed.digital_products.models import DownloadToken

        order, line = self._order(customer=None, payment_status='paid', status='processing')
        DigitalProductsPlugin().on_order_paid(order)
        token = DownloadToken.objects.get(order_item=line)
        self.assertEqual(self._render(line), f'ready|/digital/download/{token.token}/')

    def test_order_detail_shows_the_download(self):
        order, line = self._order(payment_status='unpaid', status='pending', payment_gateway='cod')
        self.client.force_login(self.buyer)
        body = self.client.get(f'/account/orders/{order.order_number}/').content.decode()
        self.assertIn(f'/account/library/{line.pk}/file/', body)

    def test_disabled_app_shows_no_download(self):
        from plugins.registry import app_registry

        _, line = self._order(payment_status='paid', status='processing')
        app_registry.deactivate('digital_products')
        self.addCleanup(app_registry.activate, 'digital_products')
        self.assertEqual(self._render(line), 'none')


class AudiobookDeliveryTests(LibraryTestCase):
    def _edition(self, product):
        from plugins.installed.audiobooks.models import Audiobook
        from plugins.installed.catalog.models import ProductVariant

        variant = ProductVariant.objects.create(
            product=product,
            name='Audiobook',
            sku=f'{product.sku}-AUDIO',
            variant_type='audiobook',
            requires_shipping=False,
        )
        return variant, Audiobook.objects.create(variant=variant, status='generating')

    def test_unnarrated_edition_never_delivers_the_books_pdf(self):
        # The e-book's PDF is passed along as the product's file; an audiobook
        # bought before its narration exists is "being prepared", not that PDF.
        from plugins.installed.digital_products.library import library
        from plugins.registry import app_registry

        variant, _ = self._edition(self.ebook)
        self._order(variant=variant, payment_status='paid', status='processing')
        [item] = library(self.buyer)
        self.assertEqual(item.state, 'preparing')
        app_registry.deactivate('audiobooks')
        self.addCleanup(app_registry.activate, 'audiobooks')
        [item] = library(self.buyer)
        self.assertEqual(item.state, 'preparing')

    def test_finished_narration_sends_the_links_a_guest_waited_for(self):
        from plugins.installed.audiobooks.services import announce_ready
        from plugins.installed.digital_products.models import DownloadToken

        variant, audiobook = self._edition(self.mug)
        order, line = self._order(
            product=self.mug, variant=variant, customer=None, payment_status='paid'
        )
        audiobook.audio_file.save('book.mp3', ContentFile(b'ID3 audio'), save=False)
        audiobook.status = 'ready'
        audiobook.save()
        announce_ready(audiobook)
        announce_ready(audiobook)  # a second announcement issues nothing twice
        self.assertEqual(DownloadToken.objects.filter(order_item=line).count(), 1)

    def test_audiobook_edition_delivers_its_narration_once_ready(self):
        from plugins.installed.audiobooks.models import Audiobook
        from plugins.installed.catalog.models import ProductVariant
        from plugins.installed.digital_products.library import library

        variant = ProductVariant.objects.create(
            product=self.mug,
            name='Audiobook',
            sku='MUG-AUDIO',
            variant_type='audiobook',
            requires_shipping=False,
        )
        audiobook = Audiobook.objects.create(variant=variant, status='generating')
        self._order(product=self.mug, variant=variant, payment_status='paid', status='processing')
        [item] = library(self.buyer)
        self.assertEqual((item.state, item.kind), ('preparing', 'audio'))
        audiobook.audio_file.save('book.mp3', ContentFile(b'ID3 audio'), save=False)
        audiobook.status = 'ready'
        audiobook.save()
        [item] = library(self.buyer)
        self.assertEqual(item.state, 'ready')
        self.assertTrue(item.listen_url.endswith('?play=1'))
        self.assertTrue(audiobook.audio_file.name.startswith('digital/audiobooks/'))
