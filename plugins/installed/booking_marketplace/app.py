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


class BookingMarketplacePlugin(Plugin):
    name = 'booking_marketplace'
    label = 'Booking marketplace'
    version = '2.0.0'
    description = (
        'Multivendor booking marketplace — vendors offer time-slot services '
        '(appointments, sessions, rentals); customers book a slot. Off by '
        'default; enable from Dashboard → Apps.'
    )
    has_models = True
    requires = ['catalog']
    enabled_by_default = False

    def ready(self) -> None:
        # Storefront /bookings/ surface — only wired while the plugin is enabled.
        self.register_urls(
            'plugins.installed.booking_marketplace.urls',
            prefix='',
            namespace='booking_marketplace',
        )

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
        ]
