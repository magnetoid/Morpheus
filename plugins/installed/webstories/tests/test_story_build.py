"""What the builder puts on each page, the poster it makes, and when a story
may be indexed.

Google's guidance for Web Stories: a poster in 3:4 portrait of at least
640×853, at least four pages (five to thirty is the range it recommends), and
short text per page. Product photos are usually square, and most products had
two or three pages, the same sentence on each.
"""

from __future__ import annotations

import io
import shutil
import tempfile
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductImage
from plugins.installed.webstories.models import MIN_INDEXABLE_PAGES, WebStory
from plugins.installed.webstories.services import BUILDER_VERSION, build_panels_for, ensure_story

_MEDIA = tempfile.mkdtemp(prefix='webstories-build-')

SHORT = (
    '<p><span>A calm, practical three-day kit for one person. '
    'Everything fits in one bag.</span></p>'
)
LONG = (
    '<p>Built from the UK Government checklist.</p>'
    '<ul><li>Six litres of water</li><li>Wind-up radio and torch</li>'
    '<li>First aid kit</li><li>Foil blanket</li><li>Whistle</li></ul>'
)


def _png(color=(240, 236, 228), size=(800, 800)) -> bytes:
    from PIL import Image

    img = Image.new('RGB', size, color)
    # A darker product in the middle, so the poster's background has to come
    # from the photo's border, not its centre.
    for x in range(300, 500):
        for y in range(300, 500):
            img.putpixel((x, y), (40, 40, 40))
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()


@override_settings(MEDIA_ROOT=_MEDIA)
class BuildTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, _MEDIA, ignore_errors=True)

    def _product(self, *, images=2, short=SHORT, description=LONG, slug='kit') -> Product:
        product = Product.objects.create(
            name='72-Hour Readiness Kit',
            slug=slug,
            sku=f'SKU-{slug}',
            status='active',
            price=Money(Decimal('89.00'), 'GBP'),
            short_description=short,
            description=description,
        )
        for i in range(images):
            pi = ProductImage(
                product=product, is_primary=(i == 0), sort_order=i, alt_text=f'View {i}'
            )
            pi.image.save(f'{slug}-{i}.png', ContentFile(_png()), save=True)
        return Product.objects.get(pk=product.pk)

    def test_pages_say_each_thing_once(self):
        panels = build_panels_for(self._product())
        kinds = [p['kind'] for p in panels]
        self.assertEqual(kinds[0], 'cover')
        self.assertEqual(kinds[-1], 'cta')
        self.assertIn('lead', kinds)
        self.assertIn('points', kinds)
        texts = [p.get('caption') for p in panels if p.get('caption')]
        self.assertEqual(len(texts), len(set(texts)), texts)
        for p in panels:
            self.assertEqual(p['v'], BUILDER_VERSION)
            for key in ('title', 'caption', 'alt'):
                self.assertNotIn('<', p.get(key) or '', p)

    def test_the_points_page_lists_the_description_bullets(self):
        panels = build_panels_for(self._product())
        points = next(p for p in panels if p['kind'] == 'points')
        self.assertEqual(points['points'][:2], ['Six litres of water', 'Wind-up radio and torch'])
        self.assertLessEqual(len(points['points']), 4)

    def test_the_lead_is_the_opening_sentences(self):
        panels = build_panels_for(self._product())
        lead = next(p for p in panels if p['kind'] == 'lead')
        self.assertTrue(lead['caption'].startswith('A calm, practical three-day kit'))
        self.assertLessEqual(len(lead['caption']), 200)

    def test_without_bullets_the_points_come_from_further_sentences(self):
        description = (
            '<p>It packs flat. It weighs under four kilos. It fits under a bed. '
            'It is checked every year.</p>'
        )
        panels = build_panels_for(self._product(short='<p>One bag.</p>', description=description))
        points = next(p for p in panels if p['kind'] == 'points')
        self.assertIn('It weighs under four kilos.', points['points'])

    def test_a_product_with_text_reaches_the_indexable_length(self):
        story, _ = ensure_story(self._product(images=1))
        self.assertGreaterEqual(story.panel_count, MIN_INDEXABLE_PAGES)
        self.assertTrue(story.is_indexable)

    def test_a_bare_product_is_too_thin_to_index(self):
        story, _ = ensure_story(self._product(images=1, short='', description='', slug='bare'))
        self.assertLess(story.panel_count, MIN_INDEXABLE_PAGES)
        self.assertFalse(story.is_indexable)

    def test_a_noindex_product_has_a_noindex_story(self):
        product = self._product(slug='hidden')
        Product.objects.filter(pk=product.pk).update(noindex=True)
        story, _ = ensure_story(Product.objects.get(pk=product.pk))
        self.assertFalse(story.is_indexable)

    def test_the_summary_is_plain_text(self):
        story, _ = ensure_story(self._product())
        self.assertEqual(
            story.summary,
            'A calm, practical three-day kit for one person. Everything fits in one bag.',
        )


@override_settings(MEDIA_ROOT=_MEDIA)
class PosterTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, _MEDIA, ignore_errors=True)

    def _product(self, slug='poster') -> Product:
        product = Product.objects.create(
            name='Poster probe',
            slug=slug,
            sku=f'SKU-{slug}',
            status='active',
            price=Money(Decimal('5.00'), 'GBP'),
            short_description='<p>One.</p><p>Two.</p>',
        )
        pi = ProductImage(product=product, is_primary=True, sort_order=0)
        pi.image.save(f'{slug}.png', ContentFile(_png()), save=True)
        return Product.objects.get(pk=product.pk)

    def _poster_name(self, story: WebStory) -> str:
        from django.conf import settings

        self.assertTrue(
            story.poster_portrait_url.startswith(settings.MEDIA_URL), story.poster_portrait_url
        )
        return story.poster_portrait_url[len(settings.MEDIA_URL) :]

    def test_the_poster_is_a_3_by_4_portrait_of_at_least_640_by_853(self):
        from PIL import Image

        story, _ = ensure_story(self._product())
        name = self._poster_name(story)
        self.assertTrue(name.startswith('webstories/posters/'))
        with default_storage.open(name) as fh:
            img = Image.open(fh)
            img.load()
        width, height = img.size
        self.assertGreaterEqual(width, 640)
        self.assertGreaterEqual(height, 853)
        self.assertEqual(width * 4, height * 3)
        self.assertEqual(img.format, 'JPEG')
        # The background is the photo's own border colour, not black.
        self.assertGreater(sum(img.getpixel((5, 5))), 600)

    def test_an_unchanged_photo_reuses_the_poster(self):
        product = self._product(slug='reuse')
        first, _ = ensure_story(product)
        second, _ = ensure_story(product)
        self.assertEqual(first.poster_portrait_url, second.poster_portrait_url)

    def test_a_new_cover_replaces_the_old_poster_file(self):
        product = self._product(slug='swap')
        first, _ = ensure_story(product)
        old = self._poster_name(first)
        image = product.images.get()
        image.image.save('swap-new.png', ContentFile(_png(color=(200, 220, 240))), save=True)
        second, _ = ensure_story(Product.objects.get(pk=product.pk))
        self.assertNotEqual(first.poster_portrait_url, second.poster_portrait_url)
        self.assertFalse(default_storage.exists(old))

    def test_a_poster_that_cannot_be_made_falls_back_to_the_photo(self):
        from unittest import mock

        # Inside the patch from the start: saving the photo already builds the
        # story through the signal, and that build must fail the same way.
        with mock.patch(
            'plugins.installed.webstories.services._render_poster', side_effect=OSError('boom')
        ):
            story, _ = ensure_story(self._product(slug='broken'))
        self.assertIn('/products/', story.poster_portrait_url)
