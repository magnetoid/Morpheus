"""Booking marketplace plugin manifest.

Multivendor *services* marketplace: vendors offer time-slot BookableServices,
customers book a slot. Reuses catalog.Vendor (a vendor can sell products via the
`marketplace` plugin AND offer bookable services here — different concept, same
owner). Ships DISABLED by default (enabled_by_default = False): the storefront
/bookings/ surface and the dashboard page appear only after the merchant turns
it on in Dashboard → Apps.
"""

from __future__ import annotations

from morpheus.app import DashboardPage, Plugin
from morpheus.core import events


class BookingMarketplacePlugin(Plugin):
    name = 'booking_marketplace'
    label = 'Booking marketplace'
    version = '1.0.0'
    description = (
        'Montenegro experience engine — bookable experiences and stays from '
        'local hosts, plus the editorial layer around them: destination guides '
        '(/places/), hotels (/hotels/) and the events calendar (/events/). '
        'Off by default; enable from Dashboard → Apps.'
    )
    has_models = True
    # cms + seo are real deps, not surfaces: the Montenegro seeders write
    # cms Pages (journal, guides) and seo Redirects/SiteSeoSettings, and the
    # sitemap/AI-feed contributions are asserted against seo's renderers.
    requires = ['catalog', 'cms', 'seo']
    enabled_by_default = False

    def ready(self) -> None:
        # Storefront /bookings/ surface — only wired while the plugin is enabled.
        self.register_urls(
            'plugins.installed.booking_marketplace.urls',
            prefix='',
            namespace='booking_marketplace',
        )
        # Header megamenu data (categories, destinations, place columns).
        # This context processor was written but never registered, so every
        # theme reading `nav_categories` / `nav_destinations` / `storefront_nav`
        # from this plugin got VariableDoesNotExist — a live 500 — instead of a
        # menu. Passed as the callable, matching orders/brand_kit/feature_adoption.
        from plugins.installed.booking_marketplace.context_processors import (  # noqa: PLC0415
            storefront_nav,
        )

        self.register_context_processor(storefront_nav)
        # Fold experiences/places/stays into seo's sitemap without seo ever
        # importing this plugin — the hook bus skips this handler for free
        # while booking_marketplace is disabled (ADR 0023).
        from plugins.installed.booking_marketplace.sitemap import contribute_sitemap_urls

        self.register_hook(events.SITEMAP_URLS, contribute_sitemap_urls, priority=50)

        # Same arrangement for /ai/products.json: this store's inventory is
        # not a catalog Product, so without this the AI shopping feed reports
        # an empty shop to every crawler.
        from plugins.installed.booking_marketplace.ai_feed import contribute_ai_feed_items

        self.register_hook(events.AI_FEED_ITEMS, contribute_ai_feed_items, priority=50)
        self.register_hook(events.HEALTH_CHECKS, self.on_health_checks, priority=45)

        # And for /llms.txt, which had the same blind spot: seo enumerates
        # catalog.Product only, so the file advertised an empty catalogue.
        from plugins.installed.booking_marketplace.llms import contribute_llms_sections

        self.register_hook(events.SEO_LLMS_SECTIONS, contribute_llms_sections, priority=50)

    def on_health_checks(self, value, **kwargs):
        """HEALTH_CHECKS: the listings and an experience page load for a visitor."""
        from core.errors.health import fetch_failures  # noqa: PLC0415
        from plugins.installed.booking_marketplace.models import BookableService  # noqa: PLC0415

        paths = ['/shop/']
        slug = (
            BookableService.objects.filter(is_active=True)
            .order_by('pk')
            .values_list('slug', flat=True)
            .first()
        )
        if slug:
            paths.append(f'/bookings/{slug}/')
        failures = fetch_failures(paths)
        value.append(
            {'name': 'Booking pages load', 'ok': not failures, 'detail': '; '.join(failures)}
        )
        return value

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Bookings',
                slug='bookings',
                view='plugins.installed.booking_marketplace.dashboard.bookings_list',
                icon='calendar-check',
                section='marketplace',
                order=60,
                nav='main',
            ),
            DashboardPage(
                label='Enquiries',
                slug='enquiries',
                view='plugins.installed.booking_marketplace.dashboard.enquiries_list',
                icon='inbox',
                section='marketplace',
                order=61,
                nav='main',
            ),
            DashboardPage(
                label='Stays',
                slug='stays',
                view='plugins.installed.booking_marketplace.dashboard.stays_list',
                icon='bed',
                section='marketplace',
                order=62,
                nav='main',
            ),
        ]
