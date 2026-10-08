"""SITEMAP_URLS contribution: booking_marketplace folds its own routes
(experiences, places, stays, the three list pages) into the seo plugin's
sitemap via the hook bus — seo never imports this plugin directly."""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.booking_marketplace.sitemap import contribute_sitemap_urls


def _vendor(slug='sitemap-vendor', is_active=True):
    from plugins.installed.catalog.models import Vendor

    return Vendor.objects.create(name='Sitemap Vendor', slug=slug, is_active=is_active)


class ContributeSitemapUrlsTests(TestCase):
    def test_active_experience_contributed_inactive_excluded(self):
        from plugins.installed.booking_marketplace.models import BookableService

        vendor = _vendor()
        BookableService.objects.create(
            vendor=vendor, name='Active exp', slug='active-slug', is_active=True
        )
        BookableService.objects.create(
            vendor=vendor, name='Inactive exp', slug='inactive-slug', is_active=False
        )

        urls = [e['loc'] for e in contribute_sitemap_urls([])]
        self.assertTrue(any('/bookings/active-slug/' in u for u in urls))
        self.assertFalse(any('inactive-slug' in u for u in urls))

    def test_inactive_vendor_rows_excluded(self):
        from plugins.installed.booking_marketplace.models import BookableService, Property

        dead_vendor = _vendor(slug='dead-vendor', is_active=False)
        BookableService.objects.create(
            vendor=dead_vendor, name='Orphan exp', slug='orphan-exp-slug', is_active=True
        )
        Property.objects.create(
            vendor=dead_vendor, name='Orphan stay', slug='orphan-stay-slug', is_active=True
        )

        urls = [e['loc'] for e in contribute_sitemap_urls([])]
        self.assertFalse(any('orphan-exp-slug' in u for u in urls))
        self.assertFalse(any('orphan-stay-slug' in u for u in urls))

    def test_active_place_contributed_inactive_excluded(self):
        from plugins.installed.booking_marketplace.models import Place

        Place.objects.create(name='Active place', slug='active-place', is_active=True)
        Place.objects.create(name='Inactive place', slug='inactive-place', is_active=False)

        urls = [e['loc'] for e in contribute_sitemap_urls([])]
        self.assertTrue(any('/places/active-place/' in u for u in urls))
        self.assertFalse(any('inactive-place' in u for u in urls))

    def test_active_stay_contributed_inactive_excluded(self):
        from plugins.installed.booking_marketplace.models import Property

        vendor = _vendor(slug='stay-vendor')
        Property.objects.create(
            vendor=vendor, name='Active stay', slug='active-stay', is_active=True
        )
        Property.objects.create(
            vendor=vendor, name='Inactive stay', slug='inactive-stay', is_active=False
        )

        urls = [e['loc'] for e in contribute_sitemap_urls([])]
        self.assertTrue(any('/hotels/active-stay/' in u for u in urls))
        self.assertFalse(any('inactive-stay' in u for u in urls))

    def test_a_list_page_is_included_only_with_something_on_it(self):
        """An empty list page answers 200 with "nothing here" — a soft 404 the
        sitemap must not invite crawlers to (it used to list all of them always)."""
        from plugins.installed.booking_marketplace.models import BookableService, Place

        urls = [e['loc'] for e in contribute_sitemap_urls([])]
        for path in ('/bookings/', '/places/', '/hotels/', '/shop/', '/regions/'):
            self.assertFalse(any(u.endswith(path) for u in urls), path)

        BookableService.objects.create(
            vendor=_vendor(), name='Kayak', slug='kayak-x', region='kotor', is_active=True
        )
        Place.objects.create(name='Kotor', slug='kotor-x', region='kotor')
        urls = [e['loc'] for e in contribute_sitemap_urls([])]
        self.assertTrue(any(u.endswith('/bookings/') for u in urls))
        self.assertTrue(any(u.endswith('/places/') for u in urls))
        self.assertTrue(any(u.endswith('/regions/') for u in urls))
        self.assertTrue(any(u.endswith('/regions/kotor/') for u in urls))
        self.assertFalse(any(u.endswith('/hotels/') for u in urls), 'no stays yet')

    def test_preserves_incoming_value(self):
        seed = [{'loc': 'https://example.test/existing/'}]
        urls = [e['loc'] for e in contribute_sitemap_urls(seed)]
        self.assertIn('https://example.test/existing/', urls)


class RenderedSitemapIncludesContributionTests(TestCase):
    """End-to-end: booking_marketplace is active (migration 0002 enables it
    by default in this deployment), so its hook fires when seo renders the
    real sitemap. booking_marketplace importing seo is fine — only the
    reverse direction is forbidden."""

    def test_rendered_sitemap_includes_active_experience(self):
        from plugins.installed.booking_marketplace.models import BookableService
        from plugins.installed.seo.services.sitemaps import render_sitemap_xml

        BookableService.objects.create(
            vendor=_vendor(slug='render-vendor'),
            name='Render exp',
            slug='render-active-slug',
            is_active=True,
        )
        xml = render_sitemap_xml()
        self.assertIn('/bookings/render-active-slug/', xml)
