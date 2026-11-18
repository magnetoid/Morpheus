"""An image a trained model made keeps saying so in every copy (v0.177.0).

EU AI Act Art. 50, and Google Merchant Center asks for it: an uploaded image whose
XMP declares an IPTC ``DigitalSourceType`` of ``trainedAlgorithmicMedia`` (or
``compositeWithTrainedAlgorithmicMedia``) used to lose it in every WebP and AVIF
copy ``/img/`` made. A copy now carries that statement and nothing else of its
source's metadata, under a cache name and an address of its own, and the Product
graph names the image as an ImageObject with ``digitalSourceType``. An image that
declares nothing is served and described as before.
"""

from __future__ import annotations

import io
import os
import shutil
import tempfile
from decimal import Decimal

from django.core.cache import cache
from django.template import Context, Template
from django.test import TestCase, override_settings
from djmoney.money import Money
from PIL import Image

from core.seo_page import KIND_PRODUCT, SeoPage
from plugins.installed.seo.services import images

_NEWSCODES = 'http://cv.iptc.org/newscodes/digitalsourcetype/'


def _packet(source_type: str, *, element: bool = False) -> bytes:
    """An XMP packet the way image tools write one, with a creator to leave behind."""
    value = f'{_NEWSCODES}{source_type}'
    attr = '' if element else f' Iptc4xmpExt:DigitalSourceType="{value}"'
    child = (
        f'<Iptc4xmpExt:DigitalSourceType>{value}</Iptc4xmpExt:DigitalSourceType>' if element else ''
    )
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
        'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" '
        'xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/" '
        f'xmlns:dc="http://purl.org/dc/elements/1.1/"{attr}>'
        f'{child}<dc:creator>Jane Photographer</dc:creator>'
        '</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
    ).encode()


class PacketTests(TestCase):
    def test_the_ai_source_types_are_read(self):
        for kind in images.AI_SOURCE_TYPES:
            with self.subTest(kind=kind):
                self.assertEqual(images.source_type_of(_packet(kind)), kind)
                self.assertEqual(images.source_type_of(_packet(kind, element=True)), kind)

    def test_other_sources_and_no_packet_say_nothing(self):
        self.assertEqual(images.source_type_of(_packet('digitalCapture')), '')
        self.assertEqual(images.source_type_of(_packet('algorithmicMedia')), '')
        self.assertEqual(images.source_type_of(b''), '')
        # The newscode without the property is not a statement.
        self.assertEqual(images.source_type_of(f'{_NEWSCODES}trainedAlgorithmicMedia'), '')

    def test_the_packet_written_says_only_that(self):
        packet = images.xmp_packet('trainedAlgorithmicMedia')
        self.assertEqual(images.source_type_of(packet), 'trainedAlgorithmicMedia')
        self.assertNotIn(b'creator', packet)


class _MediaRootMixin:
    def setUp(self):
        super().setUp()
        cache.clear()
        self.media = tempfile.mkdtemp(prefix='seo-ai-img-')
        self.addCleanup(shutil.rmtree, self.media, True)
        override = override_settings(MEDIA_ROOT=self.media, MEDIA_URL='/media/')
        override.enable()
        self.addCleanup(override.disable)
        images._read_source_type.cache_clear()
        self.addCleanup(images._read_source_type.cache_clear)

    def _image(self, rel: str, fmt: str = 'JPEG', source_type: str = '') -> str:
        path = os.path.join(self.media, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        extra = {}
        if source_type and fmt == 'PNG':
            from PIL.PngImagePlugin import PngInfo

            info = PngInfo()
            info.add_itxt('XML:com.adobe.xmp', _packet(source_type).decode())
            extra = {'pnginfo': info}
        elif source_type:
            extra = {'xmp': _packet(source_type)}
        Image.new('RGB', (900, 600), 'teal').save(path, fmt, **extra)
        return path

    def _xmp(self, path_or_bytes) -> bytes:
        src = io.BytesIO(path_or_bytes) if isinstance(path_or_bytes, bytes) else path_or_bytes
        with Image.open(src) as im:
            return bytes(im.info.get('xmp') or b'')


class CopyTests(_MediaRootMixin, TestCase):
    def test_a_copy_carries_the_statement_and_nothing_else(self):
        for fmt, source in (('JPEG', 'products/ai.jpg'), ('PNG', 'products/ai.png')):
            src = self._image(source, fmt, 'trainedAlgorithmicMedia')
            for out in images.ALLOWED_IMAGE_FORMATS:
                with self.subTest(source=fmt, copy=out):
                    cache_abs = images.variant_cache_abs(source, 400, out)
                    images.generate_image_variant(src, cache_abs, width=400, fmt=out)
                    xmp = self._xmp(cache_abs)
                    self.assertEqual(images.source_type_of(xmp), 'trainedAlgorithmicMedia')
                    self.assertNotIn(b'Jane Photographer', xmp)

    def test_a_composite_keeps_its_own_term(self):
        src = self._image('products/edit.jpg', source_type='compositeWithTrainedAlgorithmicMedia')
        cache_abs = images.variant_cache_abs('products/edit.jpg', 400, 'avif')
        images.generate_image_variant(src, cache_abs, width=400, fmt='avif')
        self.assertEqual(
            images.source_type_of(self._xmp(cache_abs)), 'compositeWithTrainedAlgorithmicMedia'
        )

    def test_an_untagged_image_keeps_no_metadata(self):
        src = self._image('products/photo.jpg')
        cache_abs = images.variant_cache_abs('products/photo.jpg', 400, 'webp')
        images.generate_image_variant(src, cache_abs, width=400, fmt='webp')
        self.assertEqual(self._xmp(cache_abs), b'')

    def test_a_tagged_copy_is_cached_under_its_own_name(self):
        self._image('products/ai.jpg', source_type='trainedAlgorithmicMedia')
        self._image('products/photo.jpg')
        self.assertTrue(
            images.variant_cache_abs('products/ai.jpg', 400, 'avif').endswith('ai.jpg.ai.avif')
        )
        self.assertTrue(
            images.variant_cache_abs('products/photo.jpg', 400, 'avif').endswith('photo.jpg.avif')
        )

    def test_the_proxy_serves_the_tagged_copy(self):
        self._image('products/ai.jpg', source_type='trainedAlgorithmicMedia')
        response = self.client.get('/img/avif/400/products/ai.jpg?ai=1')
        self.assertEqual(response.status_code, 200)
        body = b''.join(response.streaming_content)
        self.assertEqual(images.source_type_of(self._xmp(body)), 'trainedAlgorithmicMedia')


def _tag(src: str) -> str:
    return Template('{% load seo %}{% seo_responsive_image src alt="Cover" %}').render(
        Context({'src': src})
    )


class AddressTests(_MediaRootMixin, TestCase):
    def test_a_tagged_image_has_an_address_of_its_own(self):
        self._image('products/ai.jpg', source_type='trainedAlgorithmicMedia')
        html = _tag('/media/products/ai.jpg')
        self.assertIn('src="/img/webp/1200/products/ai.jpg?ai=1"', html)
        self.assertIn('/img/avif/400/products/ai.jpg?ai=1 400w', html)

    def test_an_untagged_image_keeps_its_address(self):
        self._image('products/photo.jpg')
        html = _tag('/media/products/photo.jpg')
        self.assertIn('src="/img/webp/1200/products/photo.jpg"', html)
        self.assertNotIn('?ai=', html)


class StructuredDataTests(_MediaRootMixin, TestCase):
    def _graph_product(self, *rels) -> dict:
        from plugins.installed.catalog.models import Product, ProductImage
        from plugins.installed.seo.schema import build_graph

        product = Product.objects.create(
            name='Lantern',
            slug='lantern',
            sku='LAN-1',
            status='active',
            price=Money(Decimal('20'), 'USD'),
        )
        # bulk_create: a save would make its own copies through the test storage.
        ProductImage.objects.bulk_create(
            ProductImage(product=product, image=rel, is_primary=i == 0, sort_order=i)
            for i, rel in enumerate(rels)
        )
        graph = build_graph(
            SeoPage(
                kind=KIND_PRODUCT,
                obj=product,
                rendered={
                    'slug': product.slug,
                    'name': product.name,
                    'price': {'amount': '20.00', 'currency': 'USD'},
                },
                path=f'/products/{product.slug}/',
                title=product.name,
            )
        )
        return next(n for n in graph['@graph'] if 'Product' in str(n.get('@type', '')))

    def test_a_tagged_image_is_an_image_object_saying_so(self):
        self._image('products/ai.jpg', source_type='trainedAlgorithmicMedia')
        self._image('products/photo.jpg')
        node = self._graph_product('products/ai.jpg', 'products/photo.jpg')
        tagged, plain = node['image']
        self.assertEqual(tagged['@type'], 'ImageObject')
        self.assertTrue(tagged['contentUrl'].endswith('/media/products/ai.jpg'))
        self.assertEqual(
            tagged['digitalSourceType'], 'https://schema.org/TrainedAlgorithmicMediaDigitalSource'
        )
        self.assertIsInstance(plain, str)
        # digitalSourceType is a CreativeWork property: never the Product's.
        self.assertNotIn('digitalSourceType', node)

    def test_untagged_images_stay_addresses(self):
        self._image('products/photo.jpg')
        node = self._graph_product('products/photo.jpg')
        self.assertIsInstance(node['image'], str)
