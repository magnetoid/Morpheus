"""Images and speed (v0.159.1, release 5 of the SEO and analytics audit).

- ``{% seo_responsive_image %}`` writes the image's own width and height, read
  from its file, so the browser keeps its box before it loads; seo's
  zero-specificity rule keeps every theme's own sizing.
- og:image carries its size only when the store's own file says it.
- A page that names no share image falls back to its first listed item's
  image, after the merchant's defaults, read without evaluating a queryset.
- Field Core Web Vitals: one beacon, contributed to every theme; readings from
  real browsers only, capped per day, the 75th percentile over 28 days, pruned.
- The travel themes' images and maps: ``booking_marketplace/tests/test_theme_images_and_maps.py``.
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.template import Context, Template
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from PIL import Image

from plugins.installed.seo import web_vitals
from plugins.installed.seo.services.images import image_size

THEMES = Path(__file__).resolve().parents[4] / 'themes' / 'library'
CHROME = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
PHONE = 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36'


class _MediaRoot:
    """A temporary MEDIA_ROOT holding real image files."""

    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media, MEDIA_URL='/media/')
        override.enable()
        self.addCleanup(override.disable)

    def image(self, name: str, size: tuple[int, int]) -> str:
        path = Path(self.media) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', size, (200, 120, 40)).save(path)
        return name


def _tag(src, **context) -> str:
    return Template('{% load seo %}{% seo_responsive_image src alt=alt|default:"Cover" %}').render(
        Context({'src': src, **context})
    )


class ResponsiveImageSizeTests(_MediaRoot, SimpleTestCase):
    def test_a_large_image_gets_the_box_of_the_largest_variant(self):
        self.image('products/wide.png', (2000, 1000))
        html = _tag('/media/products/wide.png')
        # The /img/ fallback is 1200 wide, so its box is 1200 x 600.
        self.assertIn('width="1200" height="600" data-sized', html)

    def test_a_small_image_keeps_its_own_size(self):
        self.image('products/small.png', (300, 200))
        self.assertIn('width="300" height="200" data-sized', _tag('/media/products/small.png'))

    def test_a_missing_file_gets_no_size(self):
        html = _tag('/media/products/gone.png')
        self.assertIn('<picture>', html)
        self.assertNotIn('width=', html)
        self.assertNotIn('data-sized', html)

    def test_only_the_stores_own_files_are_measured(self):
        self.image('products/x.png', (10, 10))
        self.assertEqual(image_size('/media/products/x.png'), (10, 10))
        self.assertEqual(image_size('https://cdn.example.com/media/products/x.png'), (10, 10))
        self.assertIsNone(image_size('/media/../etc/passwd'))
        self.assertIsNone(image_size('/elsewhere/x.png'))
        self.assertIsNone(image_size(''))

    def test_a_replaced_file_is_measured_again(self):
        self.image('products/swap.png', (100, 50))
        self.assertEqual(image_size('/media/products/swap.png'), (100, 50))
        path = Path(self.media) / 'products' / 'swap.png'
        Image.new('RGB', (40, 80)).save(path)
        stat = path.stat()
        import os

        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
        self.assertEqual(image_size('/media/products/swap.png'), (40, 80))

    def test_a_photo_turned_by_exif_is_measured_and_encoded_upright(self):
        from plugins.installed.seo.services.images import generate_image_variant

        path = Path(self.media) / 'products' / 'phone.jpg'
        path.parent.mkdir(parents=True, exist_ok=True)
        exif = Image.Exif()
        exif[0x0112] = 6  # stored landscape, shown portrait
        Image.new('RGB', (200, 100)).save(path, exif=exif)
        self.assertEqual(image_size('/media/products/phone.jpg'), (100, 200))
        out = generate_image_variant(
            str(path), str(Path(self.media) / 'v.webp'), width=400, fmt='webp'
        )
        with Image.open(out) as im:
            self.assertEqual(im.size, (100, 200))

    def test_alt_text_is_escaped_once(self):
        html = _tag('/media/products/a.png', alt='Rafting & lunch "Tara"')
        self.assertIn('alt="Rafting &amp; lunch &quot;Tara&quot;"', html)
        # A blocktrans asvar (the travel cards) is already escaped: not twice.
        html = Template(
            '{% load seo i18n %}{% blocktrans asvar a with n=name %}{{ n }} in Kotor{% endblocktrans %}'
            '{% seo_responsive_image src alt=a %}'
        ).render(Context({'src': '/media/products/a.png', 'name': 'Wine & cheese'}))
        self.assertIn('alt="Wine &amp; cheese in Kotor"', html)
        self.assertNotIn('&amp;amp;', html)


class ShareImageSizeTests(_MediaRoot, TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_the_head_states_the_size_its_file_has(self):
        from core.models import StoreSettings

        StoreSettings.objects.create(
            default_social_image=self.image('store/square.png', (800, 800))
        )
        head = self.client.get('/').content.decode().split('</head>', 1)[0]
        self.assertRegex(head, r'<meta property="og:image" content="[^"]*square\.png"')
        self.assertIn('<meta property="og:image:width" content="800">', head)
        self.assertIn('<meta property="og:image:height" content="800">', head)

    def test_an_image_on_another_host_claims_no_size(self):
        from plugins.installed.seo.head import builder

        self.image('store/square.png', (800, 800))
        self.assertFalse(builder._same_site('https://cdn.example.org/media/store/square.png'))
        self.assertTrue(builder._same_site('/media/store/square.png'))


class FirstItemImageTests(TestCase):
    def test_graphql_dicts_snake_case_dicts_and_models(self):
        from plugins.installed.seo.pages.resolve import _first_item_image

        self.assertEqual(
            _first_item_image(
                {'products': [{'primaryImage': None}, {'primaryImage': {'url': '/media/b.jpg'}}]}
            ),
            '/media/b.jpg',
        )
        self.assertEqual(
            _first_item_image({'entries': [{'image': '/media/c.jpg'}]}), '/media/c.jpg'
        )
        field = mock.Mock(url='/media/d.jpg')
        row = mock.Mock(spec=['image'], image=field)
        self.assertEqual(
            _first_item_image({'posts': [mock.Mock(spec=['primary_image'], primary_image=row)]}),
            '/media/d.jpg',
        )
        self.assertEqual(_first_item_image({'products': 'not a list', 'page_obj': None}), '')

    def test_a_queryset_is_read_with_a_limit(self):
        from plugins.installed.catalog.models import Product
        from plugins.installed.seo.pages.resolve import _first_item_image

        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(_first_item_image({'products': Product.objects.all()}), '')
        sql = ' '.join(q['sql'] for q in queries.captured_queries)
        self.assertIn('LIMIT 6', sql)

    def test_the_merchants_defaults_come_first(self):
        from plugins.installed.seo.services import resolve_meta

        meta = resolve_meta(
            obj=None, fallback_title='t', fallback_image='', last_resort_image='/media/item.jpg'
        )
        self.assertTrue(meta.og_image.endswith('/media/item.jpg'))
        meta = resolve_meta(
            obj=None,
            fallback_title='t',
            fallback_image='/media/page.jpg',
            last_resort_image='/media/item.jpg',
        )
        self.assertTrue(meta.og_image.endswith('/media/page.jpg'))


class StorefrontBlocksTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_the_image_box_rule_and_one_beacon_reach_the_page(self):
        html = self.client.get('/', HTTP_USER_AGENT=CHROME).content.decode()
        head = html.split('</head>', 1)[0]
        self.assertIn(':where(img[data-sized]){width:auto;height:auto}', head)
        self.assertEqual(html.count('web-vitals@4.2.4'), 1)
        self.assertIn(reverse('seo:web_vitals'), html)

    def test_no_theme_carries_its_own_beacon(self):
        for base in THEMES.glob('*/templates/**/*.html'):
            self.assertNotIn('web-vitals', base.read_text(), base)


class WebVitalReadingTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_a_browser_reading_is_kept_with_its_device_and_path(self):
        from plugins.installed.seo.models import WebVitalSample

        self.assertTrue(
            web_vitals.record(metric='lcp', value=2100, path='/p/?utm_source=x', user_agent=CHROME)
        )
        self.assertTrue(web_vitals.record(metric='CLS', value=0, path='/', user_agent=PHONE))
        rows = {r.metric: r for r in WebVitalSample.objects.all()}
        self.assertEqual(
            (rows['LCP'].device, rows['LCP'].path, rows['LCP'].value), ('desktop', '/p/', 2100.0)
        )
        self.assertEqual(rows['CLS'].device, 'mobile')

    def test_crawlers_test_browsers_and_odd_values_are_dropped(self):
        from plugins.installed.seo.models import WebVitalSample

        for ua in (
            '',
            'Googlebot/2.1 (+http://www.google.com/bot.html)',
            'Mozilla/5.0 Chrome-Lighthouse',
            'HeadlessChrome/130',
        ):
            self.assertFalse(web_vitals.record(metric='LCP', value=1000, user_agent=ua), ua)
        for metric, value in (
            ('FCP', 10),
            ('LCP', -1),
            ('LCP', 500_000),
            ('CLS', 60),
            ('INP', 'fast'),
            ('INP', None),
        ):
            self.assertFalse(
                web_vitals.record(metric=metric, value=value, user_agent=CHROME), (metric, value)
            )
        self.assertEqual(WebVitalSample.objects.count(), 0)

    def test_a_day_keeps_at_most_the_cap(self):
        with mock.patch.object(web_vitals, 'DAILY_CAP', 2):
            results = [
                web_vitals.record(metric='INP', value=80, user_agent=CHROME) for _ in range(3)
            ]
            self.assertEqual(results, [True, True, False])
            # Each metric has its own count.
            self.assertTrue(web_vitals.record(metric='LCP', value=900, user_agent=CHROME))

    def test_the_summary_is_googles_p75_in_googles_units(self):
        from core.utils.site import store_today
        from plugins.installed.seo.models import WebVitalSample

        today = store_today()
        rows = [('LCP', v) for v in (1000, 2000, 3000, 4000, 5000)]
        rows += [('INP', v) for v in (100, 200, 300, 400)]
        rows += [('CLS', 0.0)] * 3
        WebVitalSample.objects.bulk_create(
            WebVitalSample(day=today, metric=m, value=v) for m, v in rows
        )
        WebVitalSample.objects.create(day=today - timedelta(days=28), metric='LCP', value=90_000)
        out = web_vitals.summary()
        self.assertEqual(out, {'lcp': 4.0, 'inp': 300, 'cls': 0.0, 'samples': 12})
        self.assertEqual(web_vitals.summary(device='mobile')['samples'], 0)

        from plugins.installed.seo.services import cwv_summary

        self.assertEqual(cwv_summary(), out)

    def test_prune_keeps_only_googles_window(self):
        from core.utils.site import store_today
        from plugins.installed.seo.models import WebVitalSample

        today = store_today()
        WebVitalSample.objects.create(day=today - timedelta(days=27), metric='LCP', value=1)
        WebVitalSample.objects.create(day=today - timedelta(days=28), metric='LCP', value=2)
        self.assertEqual(web_vitals.prune(), 1)
        self.assertEqual(list(WebVitalSample.objects.values_list('value', flat=True)), [1.0])


class BeaconViewTests(TestCase):
    def setUp(self):
        cache.clear()
        # sendBeacon carries no CSRF token, and a real browser is held to the check.
        self.client = Client(enforce_csrf_checks=True)
        self.url = reverse('seo:web_vitals')

    def post(self, body, ua=CHROME):
        return self.client.post(self.url, body, content_type='text/plain', HTTP_USER_AGENT=ua)

    def test_a_reading_is_stored(self):
        from plugins.installed.seo.models import WebVitalSample

        resp = self.post('{"name": "LCP", "value": 1800, "rating": "good", "url": "/books/"}')
        self.assertEqual((resp.status_code, resp.json()), (200, {'ok': True}))
        self.assertEqual(WebVitalSample.objects.get().path, '/books/')

    def test_a_crawler_is_answered_and_not_stored(self):
        from plugins.installed.seo.models import WebVitalSample

        resp = self.post('{"name": "LCP", "value": 1800}', ua='Googlebot/2.1')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(WebVitalSample.objects.exists())

    def test_anything_else_is_refused(self):
        from plugins.installed.seo.models import WebVitalSample

        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(
            self.post('{"name": "LCP", "value": 1, "pad": "' + 'x' * 3000 + '"}').status_code, 400
        )
        self.assertEqual(self.post('[1, 2]').status_code, 400)
        self.assertEqual(self.post('not json').status_code, 400)
        self.assertFalse(WebVitalSample.objects.exists())

    def test_the_prune_task_is_scheduled_by_its_registered_name(self):
        from django.conf import settings

        import plugins.installed.seo.tasks  # noqa: F401 — the worker imports it by autodiscovery
        from morph.celery import app

        names = {entry['task'] for entry in settings.CELERY_BEAT_SCHEDULE.values()}
        self.assertIn('seo.prune_web_vitals', names)
        self.assertIn('seo.prune_web_vitals', app.tasks)


class PageSpeedCardTests(TestCase):
    def test_a_layout_that_never_shifts_shows_zero_not_a_dash(self):
        from core.utils.site import store_today
        from plugins.installed.seo.models import WebVitalSample

        WebVitalSample.objects.create(day=store_today(), metric='CLS', value=0.0)
        staff = get_user_model().objects.create_superuser(
            username='speed', email='speed@example.com', password='x'
        )
        self.client.force_login(staff)
        html = self.client.get('/dashboard/seo/').content.decode()
        card = html.split('data-cwv-card', 1)[1].split('</div>\n  </div>', 1)[0]
        self.assertIn('0.000', card)
        self.assertIn('1 reading in 28 days', html)


class ThemePageCssTests(SimpleTestCase):
    """A home page's CSS sits in the head: below the markup, dotbooks' hero laid
    out unstyled and then jumped (CLAUDE.md, the PDP CLS landmine)."""

    def test_no_home_page_styles_its_content_from_below(self):
        homes = sorted(THEMES.glob('*/templates/storefront/home.html'))
        self.assertGreaterEqual(len(homes), 5)
        for home in homes:
            text = home.read_text()
            content = text.find('{% block content %}')
            self.assertNotEqual(content, -1, home)
            self.assertNotIn('<style', text[content:], home)
