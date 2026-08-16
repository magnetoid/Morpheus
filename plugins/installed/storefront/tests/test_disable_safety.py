"""Toggling an optional plugin off must never take the storefront down —
and must actually remove the plugin's surface.

The disable litmus test (CLAUDE.md) says a disabled plugin's *surface*
disappears. There is a sharper failure mode underneath it: a shell or theme
that hard-references a plugin — `{% url 'seo:…' %}` in the theme `<head>` —
does not merely keep the surface, it **500s every page** the moment the plugin
is toggled off, because `deactivate()` unregisters the plugin's URLs and the
reverse fails inside the base template. The merchant sees "Turn off SEO" and
gets a dead storefront.

And the quieter failure: a shell view that imports a sibling plugin inside
`try/except` guards ABSENCE, not DISABLE — a disabled plugin is still
importable and its tables still exist, so the surface (PDP videos, CMS journal
entries, the CRM lead capture, …) survives the toggle. The storefront views
therefore gate every optional-plugin read on `app_registry.is_active()` (the
ADR 0013 pattern from `views/account.py`); the *_surface_vanishes* tests below
fail if any of those gates is removed.

This test toggles each optional plugin the storefront/theme references and
asserts the storefront still answers. Extend `OPTIONAL` as sites are repaid.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.registry import app_registry

# Unique markers — never a bare display word (the theme's own copy contains
# most words; see the `body.index('One')` landmine in CLAUDE.md).
_PRODUCT_SLUG = 'disable-safety-probe'
_VIDEO_URL = 'https://cdn.example.test/disable-safety-probe-clip-7f3a.mp4'
_JOURNAL_SLUG = 'disable-safety-probe-journal-7f3a'
_AUTHOR = 'Ines Probeauthor'
_AUTHOR_SLUG = 'ines-probeauthor'
_VENDOR_SLUG = 'probe-press-7f3a'


class StorefrontSurvivesOptionalPluginDisableTests(TestCase):
    OPTIONAL = (
        'seo',
        'cms',
        'book_product',
        'metafields',
        'product_videos',
        'crm',
        'consent',
        'marketplace',
    )

    def setUp(self):
        cache.clear()  # a cached page fragment would hide a render failure
        from plugins.installed.book_product.models import BookProduct
        from plugins.installed.catalog.models import Product, Vendor
        from plugins.installed.cms.models import Page
        from plugins.installed.product_videos.models import ProductVideo

        self.vendor = Vendor.objects.create(
            name='Probe Press', slug=_VENDOR_SLUG, description='A probe press.'
        )
        self.product = Product.objects.create(
            name='Disable Safety Probe',
            slug=_PRODUCT_SLUG,
            sku='DSP-1',
            price=Money(Decimal('12.00'), 'USD'),
            product_type='simple',
            status='active',
            vendor=self.vendor,
        )
        BookProduct.objects.create(product=self.product, author=_AUTHOR)
        ProductVideo.objects.create(product=self.product, url=_VIDEO_URL, title='Probe clip')
        # publish_at is what the journal orders on; the seeded editorial pages
        # carry one, so a fresh entry must be dated to make the home's top-3.
        Page.objects.create(
            slug=_JOURNAL_SLUG,
            title='Probe journal entry',
            state='published',
            publish_at=timezone.now() - timedelta(minutes=1),
            metadata={'category': 'journal'},
        )

    def _toggle_off(self, name):
        self.assertTrue(app_registry.is_active(name), f'{name} should start active')
        app_registry.deactivate(name)
        cache.clear()

    def _toggle_on(self, name):
        app_registry.activate(name)
        cache.clear()
        self.assertTrue(app_registry.is_active(name))

    def test_storefront_renders_with_each_optional_plugin_disabled(self):
        author_path = f'/author/{_AUTHOR_SLUG}/'
        paths = (
            '/',
            '/products/',
            '/journal/',
            f'/products/{_PRODUCT_SLUG}/',
            author_path,
            f'/vendor/{_VENDOR_SLUG}/',
            '/marketplace/',
        )
        for name in self.OPTIONAL:
            with self.subTest(plugin=name):
                self._toggle_off(name)
                try:
                    for path in paths:
                        r = self.client.get(path)
                        # The author landing IS a book_product surface (its
                        # bibliography + slug resolution live there): with the
                        # plugin off it 404s — the surface is gone, not broken.
                        expected = 404 if (name == 'book_product' and path == author_path) else 200
                        self.assertEqual(
                            r.status_code,
                            expected,
                            f'{path} returned {r.status_code} with {name} disabled',
                        )
                finally:
                    self._toggle_on(name)

    def test_product_videos_surface_vanishes_on_disable(self):
        path = f'/products/{_PRODUCT_SLUG}/'
        body = self.client.get(path).content.decode()
        self.assertIn(_VIDEO_URL, body, 'video should render while product_videos is active')

        self._toggle_off('product_videos')
        try:
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200)
            self.assertNotIn(_VIDEO_URL, r.content.decode())
        finally:
            self._toggle_on('product_videos')

    def test_cms_journal_surface_vanishes_on_disable(self):
        from plugins.installed.storefront.views.content import _JOURNAL_ENTRIES

        marker = f'/journal/{_JOURNAL_SLUG}/'
        seeded_marker = f'/journal/{_JOURNAL_ENTRIES[0]["slug"]}/'
        for path in ('/journal/', '/'):
            with self.subTest(path=path):
                body = self.client.get(path).content.decode()
                self.assertIn(marker, body, f'CMS journal entry should list on {path} while active')

        self._toggle_off('cms')
        try:
            for path in ('/journal/', '/'):
                with self.subTest(path=path):
                    r = self.client.get(path)
                    self.assertEqual(r.status_code, 200)
                    body = r.content.decode()
                    self.assertNotIn(marker, body)
                    # The seeded editorial set takes over — same fallback as
                    # a store with no CMS at all.
                    self.assertIn(seeded_marker, body)
        finally:
            self._toggle_on('cms')

    def test_crm_contact_capture_vanishes_on_disable(self):
        from plugins.installed.crm.models import Lead

        def _post(email):
            return self.client.post(
                '/contact/', {'email': email, 'name': 'Probe Lead', 'message': 'hello there'}
            )

        r_on = _post('probe-lead-on@example.test')
        self.assertEqual(r_on.status_code, 200)
        self.assertTrue(Lead.objects.filter(email='probe-lead-on@example.test').exists())

        self._toggle_off('crm')
        try:
            r_off = _post('probe-lead-off@example.test')
            # The form still succeeds for the shopper — same response as when
            # crm is on — it just doesn't write a lead into a disabled plugin.
            self.assertEqual(r_off.status_code, r_on.status_code)
            self.assertFalse(Lead.objects.filter(email='probe-lead-off@example.test').exists())
        finally:
            self._toggle_on('crm')
