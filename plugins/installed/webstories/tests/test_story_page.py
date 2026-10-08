"""`/story/<slug>/` names a publisher logo that exists — and that Google accepts.

`publisher-logo-src` is mandatory on an `<amp-story>`. The view read
`StoreSettings.logo_url` — a field that has never existed (the model has
`logo`) — so a merchant's uploaded logo was ignored, and every story on every
store pointed at `/static/img/logo-1x1.png`, a file that is nowhere in the tree.

The fix after that fell back to `/favicon.ico`, which every store without an
uploaded favicon serves as a small SVG. Google requires a story's publisher
logo to be a square raster image of at least 96 px, so every story on dotbooks
and supernatural carried a logo the rich results reject (found by the crawl
after v0.80.0).
"""

from __future__ import annotations

import io
import re
import shutil
import tempfile
from decimal import Decimal
from urllib.parse import urlsplit

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.webstories.models import WebStory

_MEDIA = tempfile.mkdtemp(prefix='webstories-tests-')


def _png(name='logo.png', size=(128, 128)):
    from PIL import Image

    buf = io.BytesIO()
    Image.new('RGB', size, (20, 120, 110)).save(buf, 'PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=_MEDIA)
class StoryPublisherLogoTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, _MEDIA, ignore_errors=True)

    def setUp(self):
        product = Product.objects.create(
            name='Story Probe',
            slug='story-probe',
            sku='WS-1',
            status='active',
            price=Money(Decimal('9.00'), 'USD'),
        )
        WebStory.objects.update_or_create(
            product=product,
            defaults={'is_published': True, 'panels': [{'title': 'One', 'caption': 'A panel'}]},
        )

    def _logo_src(self) -> str:
        response = self.client.get('/story/story-probe/')
        self.assertEqual(response.status_code, 200)
        match = re.search(r'publisher-logo-src="([^"]*)"', response.content.decode())
        self.assertIsNotNone(match)
        return match.group(1)

    def test_the_merchants_logo_is_the_publisher_logo(self):
        from core.models import StoreSettings

        StoreSettings.objects.all().delete()
        store = StoreSettings.objects.create(store_name='Probe Store')
        store.logo = _png()
        store.save()
        self.assertTrue(self._logo_src().endswith(store.logo.url))

    def test_without_a_logo_the_url_still_resolves(self):
        from django.conf import settings
        from django.contrib.staticfiles import finders

        path = urlsplit(self._logo_src()).path
        if path.startswith(settings.STATIC_URL):
            # The test client serves no static files; ask the finders instead.
            self.assertIsNotNone(finders.find(path[len(settings.STATIC_URL) :]), path)
        else:
            self.assertIn(self.client.get(path).status_code, (200, 302), path)

    def _assert_square_raster(self, src: str) -> None:
        from django.conf import settings
        from django.contrib.staticfiles import finders
        from PIL import Image

        path = urlsplit(src).path
        self.assertTrue(path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')), src)
        self.assertTrue(path.startswith(settings.STATIC_URL), src)
        with Image.open(finders.find(path[len(settings.STATIC_URL) :])) as img:
            self.assertEqual(img.width, img.height, src)
            self.assertGreaterEqual(img.width, 96, src)

    def test_without_a_logo_the_publisher_logo_is_a_square_raster_image(self):
        from core.models import StoreSettings

        StoreSettings.objects.all().delete()
        StoreSettings.objects.create(store_name='Probe Store')
        src = self._logo_src()
        self.assertNotIn('favicon', src)
        self._assert_square_raster(src)

    def test_a_logo_google_would_reject_is_not_the_publisher_logo(self):
        from core.models import StoreSettings

        StoreSettings.objects.all().delete()
        store = StoreSettings.objects.create(store_name='Probe Store')
        store.logo = _png('wordmark.png', size=(400, 100))
        store.save()
        src = self._logo_src()
        self.assertNotIn('wordmark', src)
        self._assert_square_raster(src)
