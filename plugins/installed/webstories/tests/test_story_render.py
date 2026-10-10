"""The rendered story: no markup as text, the AMP CTA, language, robots, and
stories built by the old builder heal on first view.

The regression for the 2026-10-10 bug renders a story whose STORED panels still
carry raw HTML (every story built before the fix): the page must not show a
tag as text even before anything rebuilds it.
"""

from __future__ import annotations

import io
import re
import shutil
import tempfile
from decimal import Decimal
from unittest import mock

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductImage
from plugins.installed.webstories.models import WebStory
from plugins.installed.webstories.services import BUILDER_VERSION, ensure_story

_MEDIA = tempfile.mkdtemp(prefix='webstories-render-')


def _png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new('RGB', (700, 700), (230, 230, 225)).save(buf, 'PNG')
    return buf.getvalue()


@override_settings(MEDIA_ROOT=_MEDIA)
class RenderTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, _MEDIA, ignore_errors=True)

    def _product(self, slug='oil', **extra) -> Product:
        product = Product.objects.create(
            name='Abyssinian Oil',
            slug=slug,
            sku=f'SKU-{slug}',
            status='active',
            price=Money(Decimal('12.00'), 'USD'),
            short_description='<p>Abyssinian Oil (<em>Crambe abyssinica</em>), cold-pressed.</p>',
            description='<ul><li>Light</li><li>Non-greasy</li><li>Fast absorbing</li></ul>',
            **extra,
        )
        for i in range(2):
            pi = ProductImage(product=product, is_primary=(i == 0), sort_order=i)
            pi.image.save(f'{slug}-{i}.png', ContentFile(_png()), save=True)
        return Product.objects.get(pk=product.pk)

    def _get(self, slug='oil') -> str:
        response = self.client.get(f'/story/{slug}/')
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_no_markup_is_shown_as_text(self):
        ensure_story(self._product())
        body = self._get()
        self.assertNotIn('&lt;', body)
        self.assertIn('Crambe abyssinica', body)
        self.assertIn('<li>Non-greasy</li>', body)

    def test_stories_stored_with_raw_html_render_clean_before_any_rebuild(self):
        product = self._product(slug='stale')
        WebStory.objects.update_or_create(
            product=product,
            defaults={
                'is_published': True,
                'summary': '<p>Stale <span>summary</span></p>',
                'panels': [
                    {
                        'image_url': '',
                        'title': 'Stale',
                        'caption': '<p><span>Old caption</span></p>',
                    },
                    {
                        'image_url': '',
                        'title': 'Shop now',
                        'caption': '<ul><li>x</li></ul>',
                        'cta_url': '/products/stale/',
                    },
                ],
            },
        )
        with mock.patch(
            'plugins.installed.webstories.services.ensure_story',
            side_effect=RuntimeError('no rebuild'),
        ):
            body = self._get('stale')
        self.assertNotIn('&lt;', body)
        self.assertIn('Old caption', body)

    def test_an_old_story_is_rebuilt_on_first_view(self):
        product = self._product(slug='heal')
        WebStory.objects.update_or_create(
            product=product,
            defaults={
                'is_published': True,
                'panels': [{'image_url': '', 'title': 'Old', 'caption': 'x'}],
            },
        )
        self._get('heal')
        story = WebStory.objects.get(product=product)
        self.assertEqual(story.panels[0]['v'], BUILDER_VERSION)
        self.assertEqual(story.panels[0]['kind'], 'cover')

    def test_the_last_page_carries_the_amp_outlink_cta(self):
        ensure_story(self._product())
        body = self._get()
        pages = body.split('<amp-story-page ')
        last = pages[-1]
        self.assertIn('<amp-story-page-outlink layout="nodisplay"', last)
        outlink = last.split('<amp-story-page-outlink', 1)[1].split('</amp-story-page-outlink>', 1)[
            0
        ]
        self.assertEqual(outlink.count('<a '), 1)
        self.assertRegex(outlink, r'href="https?://[^"]+/products/oil/"')
        # Only the last page carries one.
        self.assertEqual(body.count('<amp-story-page-outlink'), 1)

    def test_the_story_carries_the_page_language(self):
        ensure_story(self._product())
        self.assertRegex(self._get(), r'<html amp lang="en')

    def test_poster_and_logo_are_absolute(self):
        ensure_story(self._product())
        body = self._get()
        poster = re.search(r'poster-portrait-src="([^"]+)"', body).group(1)
        self.assertTrue(poster.startswith('http'), poster)

    def test_indexable_story_has_no_robots_meta(self):
        ensure_story(self._product())
        self.assertNotIn('name="robots"', self._get())

    def test_noindex_product_story_says_noindex(self):
        product = self._product(slug='prelaunch')
        Product.objects.filter(pk=product.pk).update(noindex=True)
        ensure_story(Product.objects.get(pk=product.pk))
        self.assertIn('<meta name="robots" content="noindex, follow">', self._get('prelaunch'))

    def test_pages_with_more_text_stay_longer(self):
        ensure_story(self._product())
        seconds = [int(s) for s in re.findall(r'auto-advance-after="(\d+)s"', self._get())]
        self.assertTrue(seconds)
        self.assertTrue(all(5 <= s <= 12 for s in seconds), seconds)


@override_settings(MEDIA_ROOT=_MEDIA)
class SitemapAndIndexTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, _MEDIA, ignore_errors=True)

    def _story(self, slug: str, *, noindex=False, text=True) -> None:
        product = Product.objects.create(
            name=f'P {slug}',
            slug=slug,
            sku=f'SKU-{slug}',
            status='active',
            price=Money(Decimal('3.00'), 'USD'),
            short_description='<p>One. Two. Three.</p>' if text else '',
            description='<ul><li>a</li><li>b</li></ul>' if text else '',
            noindex=noindex,
        )
        pi = ProductImage(product=product, is_primary=True, sort_order=0)
        pi.image.save(f'{slug}.png', ContentFile(_png()), save=True)
        ensure_story(Product.objects.get(pk=product.pk))

    def test_the_sitemap_lists_only_indexable_stories(self):
        from plugins.installed.seo.services.sitemaps import _iter_webstory_entries

        self._story('good')
        self._story('hidden', noindex=True)
        self._story('thin', text=False)
        locs = [e['loc'] for e in _iter_webstory_entries('https://shop.test/')]
        self.assertEqual(locs, ['https://shop.test/story/good/'])

    def test_the_index_page_is_not_the_bookshops(self):
        self._story('good')
        body = self.client.get('/stories/').content.decode()
        hero = body.split('class="stories-hero"', 1)[1].split('</section>', 1)[0]
        self.assertNotIn('book', hero.lower())
        title = body.split('<title>', 1)[1].split('</title>', 1)[0]
        self.assertTrue(title.startswith('Stories'), title)
        self.assertNotIn('dot books', title)
        self.assertIn('/story/good/', body)
        self.assertEqual(body.count('<title>'), 1)
        self.assertLessEqual(body.count('"BreadcrumbList"'), 1)


class SettingsPanelTests(TestCase):
    def test_the_panel_is_registered_and_its_key_is_read(self):
        from plugins.registry import app_registry

        panels = [e for e in app_registry.all_settings_panels() if str(e['plugin']) == 'webstories']
        self.assertEqual(len(panels), 1)
        self.assertIn('show_pdp_embed', panels[0]['panel'].schema['properties'])

    def test_switching_the_embed_off_hides_it(self):
        from django.template import Context, Template

        from plugins.registry import app_registry

        plugin = app_registry.get('webstories')
        self.addCleanup(plugin.set_config, 'show_pdp_embed', True)
        tpl = Template('{% load webstories %}{% webstory_embed_enabled as on %}{{ on }}')
        self.assertEqual(tpl.render(Context({})), 'True')
        plugin.set_config('show_pdp_embed', False)
        self.assertEqual(tpl.render(Context({})), 'False')
