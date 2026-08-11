"""Audiobooks plugin tests — model shape + the player-gating property.

Storefront/permission boundary tests land with the PDP player block (phase 3).
"""

# Lazy imports inside tests are intentional (plugin load-order isolation).
# ruff: noqa: PLC0415
from __future__ import annotations

import tempfile
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from djmoney.money import Money


class AudiobookModelTests(TestCase):
    def _audiobook_variant(self):
        from plugins.installed.catalog.models import Product, ProductVariant

        product = Product.objects.create(
            name='Test Book',
            slug='ab-book',
            sku='AB-1',
            status='active',
            price=Money(Decimal('10.00'), 'USD'),
        )
        return ProductVariant.objects.create(
            product=product,
            name='Audiobook',
            sku='AB-1-AUDIO',
            price=Money(Decimal('14.99'), 'USD'),
            variant_type='digital',
            requires_shipping=False,
        )

    def test_is_ready_requires_both_status_and_file(self):
        from plugins.installed.audiobooks.models import Audiobook

        ab = Audiobook.objects.create(variant=self._audiobook_variant(), status='none')
        self.assertFalse(ab.is_ready)
        # status='ready' alone is not enough — there must be an actual file.
        ab.status = 'ready'
        self.assertFalse(ab.is_ready)

    def test_onetoone_to_variant(self):
        from plugins.installed.audiobooks.models import Audiobook

        variant = self._audiobook_variant()
        ab = Audiobook.objects.create(variant=variant, narrator='Jane Doe', source='uploaded')
        self.assertEqual(variant.audiobook, ab)
        self.assertEqual(ab.narrator, 'Jane Doe')


class ProductFormHandlerTests(TestCase):
    """The PRODUCT_FORM_SAVED handler creates the audiobook EDITION as a real
    digital variant — only for book products."""

    def _book(self):
        from plugins.installed.book_product.models import BookProduct
        from plugins.installed.catalog.models import Product

        product = Product.objects.create(
            name='A Book',
            slug='ab-form',
            sku='ABF-1',
            status='active',
            price=Money(Decimal('9.99'), 'USD'),
        )
        BookProduct.objects.create(product=product, author='An Author')
        return product

    def test_saved_handler_creates_audiobook_variant(self):
        from plugins.installed.audiobooks.app import AudiobooksPlugin
        from plugins.installed.audiobooks.models import Audiobook

        product = self._book()
        AudiobooksPlugin().on_product_form_saved(
            product=product,
            post={
                'audiobook_enabled': '1',
                'audiobook_price': '14.99',
                'audiobook_narrator': 'Jane',
            },
            files=None,
        )
        ab = Audiobook.objects.get(variant__product=product)
        self.assertEqual(ab.narrator, 'Jane')
        # Its own edition type (not a generic 'digital' variant) — but still a
        # downloadable, no-shipping edition.
        self.assertEqual(ab.variant.variant_type, 'audiobook')
        self.assertFalse(ab.variant.requires_shipping)
        self.assertEqual(str(ab.variant.price.amount), '14.99')

    def test_audiobook_variant_is_digital_behaving_at_checkout(self):
        """The new 'audiobook' type must behave like 'digital' where it matters:
        checkout skips inventory reservation (else it would demand stock/shipping
        for a download). Regression guard for the variant-type split."""
        from plugins.installed.audiobooks.services import (
            get_or_create_audiobook_edition,
        )
        from plugins.installed.orders.services import _is_inventoried

        product = self._book()
        ab = get_or_create_audiobook_edition(product, sku='AB-INV-1')
        self.assertEqual(ab.variant.variant_type, 'audiobook')
        self.assertFalse(_is_inventoried(product, ab.variant))

    def test_non_book_product_is_ignored(self):
        # No BookProduct → product.book raises (AttributeError subclass) → the
        # guard returns cleanly and no audiobook variant is created.
        from plugins.installed.audiobooks.app import AudiobooksPlugin
        from plugins.installed.audiobooks.models import Audiobook
        from plugins.installed.catalog.models import Product

        mug = Product.objects.create(
            name='Mug',
            slug='ab-mug',
            sku='ABM-1',
            status='active',
            price=Money(Decimal('5.00'), 'USD'),
        )
        AudiobooksPlugin().on_product_form_saved(
            product=mug, post={'audiobook_enabled': '1'}, files=None
        )
        self.assertFalse(Audiobook.objects.filter(variant__product=mug).exists())


class StorefrontPlayerTests(TestCase):
    """The PDP player self-gates: `audiobook_for` returns an audiobook only when
    it's ready (status='ready' + a file), so a half-built one never shows."""

    def test_audiobook_for_returns_ready_only(self):
        from plugins.installed.audiobooks.models import Audiobook
        from plugins.installed.audiobooks.templatetags.audiobooks import audiobook_for
        from plugins.installed.catalog.models import Product, ProductVariant

        product = Product.objects.create(
            name='Book',
            slug='ab-pl',
            sku='ABPL-1',
            status='active',
            price=Money(Decimal('9.99'), 'USD'),
        )
        variant = ProductVariant.objects.create(
            product=product,
            name='Audiobook',
            sku='ABPL-1-A',
            variant_type='digital',
            requires_shipping=False,
        )
        ab = Audiobook.objects.create(variant=variant, status='none')
        self.assertIsNone(audiobook_for(product))  # not ready → hidden

        ab.audio_file = 'audiobooks/x.mp3'  # assign the name (no real file IO)
        ab.status = 'ready'
        ab.save()
        self.assertEqual(audiobook_for(product), ab)

    def test_audiobook_for_accepts_graphql_dict_product(self):
        """The storefront PDP passes `product` as a GraphQL dict, not the model.
        The tag must still resolve the audiobook — regression: filtering an FK by
        a dict raised, the bare except swallowed it, and the player never showed."""
        from plugins.installed.audiobooks.models import Audiobook
        from plugins.installed.audiobooks.templatetags.audiobooks import audiobook_for
        from plugins.installed.catalog.models import Product, ProductVariant

        product = Product.objects.create(
            name='Dict Book',
            slug='ab-dict',
            sku='ABD-1',
            status='active',
            price=Money(Decimal('9.99'), 'USD'),
        )
        variant = ProductVariant.objects.create(
            product=product,
            name='Audiobook',
            sku='ABD-1-A',
            variant_type='digital',
            requires_shipping=False,
        )
        ab = Audiobook.objects.create(
            variant=variant, status='ready', audio_file='audiobooks/x.mp3'
        )
        product_dict = {'id': str(product.pk), 'name': product.name}
        self.assertEqual(audiobook_for(product_dict), ab)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class GenerationTests(TestCase):
    """ElevenLabs generation (HTTP mocked — no real API key needed)."""

    def _audiobook(self):
        from plugins.installed.audiobooks.models import Audiobook
        from plugins.installed.book_product.models import BookProduct
        from plugins.installed.catalog.models import Product, ProductVariant

        product = Product.objects.create(
            name='A Book',
            slug='ab-gen',
            sku='ABG-1',
            status='active',
            price=Money(Decimal('9.99'), 'USD'),
        )
        BookProduct.objects.create(product=product, author='An Author', synopsis='A short tale.')
        variant = ProductVariant.objects.create(
            product=product,
            name='Audiobook',
            sku='ABG-1-A',
            variant_type='digital',
            requires_shipping=False,
        )
        return Audiobook.objects.create(variant=variant, status='none')

    @mock.patch(
        'plugins.installed.audiobooks.services._config',
        return_value={'api_key': 'k', 'voice_id': 'v', 'model': 'eleven_multilingual_v2'},
    )
    @mock.patch('plugins.installed.audiobooks.services._tts', return_value=b'FAKE_MP3_BYTES')
    def test_generate_success_sets_ready(self, _tts, _cfg):
        from plugins.installed.audiobooks.services import generate

        ab = self._audiobook()
        result = generate(ab)
        self.assertTrue(result['ok'], result)
        ab.refresh_from_db()
        self.assertEqual(ab.status, 'ready')
        self.assertEqual(ab.source, 'elevenlabs')
        self.assertTrue(ab.audio_file)
        self.assertTrue(_tts.called)

    @mock.patch(
        'plugins.installed.audiobooks.services._config',
        return_value={'api_key': '', 'voice_id': ''},
    )
    def test_generate_without_key_fails(self, _cfg):
        from plugins.installed.audiobooks.services import generate

        ab = self._audiobook()
        result = generate(ab)
        self.assertFalse(result['ok'])
        ab.refresh_from_db()
        self.assertEqual(ab.status, 'failed')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PdfNarrationSourceTests(TestCase):
    """source_text() narrates the book PDF when present, else the blurb."""

    def _audiobook(self, *, synopsis=''):
        from plugins.installed.audiobooks.models import Audiobook
        from plugins.installed.book_product.models import BookProduct
        from plugins.installed.catalog.models import Product, ProductVariant

        product = Product.objects.create(
            name='A Book',
            slug='ab-pdf',
            sku='ABP-1',
            status='active',
            price=Money(Decimal('9.99'), 'USD'),
        )
        BookProduct.objects.create(product=product, author='An Author', synopsis=synopsis)
        variant = ProductVariant.objects.create(
            product=product,
            name='Audiobook',
            sku='ABP-1-A',
            variant_type='digital',
            requires_shipping=False,
        )
        return Audiobook.objects.create(variant=variant)

    def _pdf_bytes(self, text):
        import io

        from reportlab.pdfgen import canvas

        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(72, 720, text)
        c.showPage()
        c.save()
        return buf.getvalue()

    def test_source_text_prefers_pdf_over_blurb(self):
        from django.core.files.base import ContentFile

        from plugins.installed.audiobooks.services import source_text

        ab = self._audiobook(synopsis='Marketing blurb only.')
        ab.source_pdf.save(
            'book.pdf', ContentFile(self._pdf_bytes('The real book body text.')), save=True
        )
        text = source_text(ab)
        self.assertIn('real book body text', text)
        self.assertNotIn('Marketing blurb', text)

    def test_source_text_falls_back_to_blurb_without_pdf(self):
        from plugins.installed.audiobooks.services import source_text

        ab = self._audiobook(synopsis='A short tale.')
        text = source_text(ab)
        self.assertIn('short tale', text)
