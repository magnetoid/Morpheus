"""live_commerce — live shopping events MVP.

A scheduled event with an embedded stream and pinned, buyable products.
Everything is contributed: storefront routes via register_urls, the home
teaser via a StorefrontBlock, dashboard CRUD via register_urls + a
DashboardPage. Conversion is measured through the existing UTM/attribution
pipeline (no analytics beacon changes).
"""

from __future__ import annotations

from morpheus.app import DashboardCard, DashboardPage, Plugin, StorefrontBlock
from morpheus.core import events


class LiveCommercePlugin(Plugin):
    name = 'live_commerce'
    label = 'Live commerce'
    version = '1.0.0'
    description = (
        'Scheduled live shopping events: embedded stream, pinned buyable products, '
        'and UTM-attributed conversion. Replay when a recording URL is set.'
    )
    has_models = True
    requires = ['catalog', 'orders']

    def ready(self) -> None:
        self.register_hook(events.DASHBOARD_SEARCH, self.on_dashboard_search)
        self.register_urls(
            'plugins.installed.live_commerce.urls',
            prefix='dashboard/live/',
            namespace='live_commerce',
        )
        self.register_urls(
            'plugins.installed.live_commerce.urls_storefront',
            prefix='',
            namespace='live_commerce_storefront',
        )

    def on_dashboard_search(self, value, query='', words=None, **kwargs):
        """Live events (by title) in the dashboard's search box."""
        from plugins import dashboard_search as ds
        from plugins.installed.live_commerce.models import LiveEvent

        return ds.add(
            value,
            LiveEvent,
            query,
            words,
            fields=('title', 'slug'),
            section='Live events',
            kind='live_event',
            icon='video',
            capability='cms.write',
            label=lambda e: e.title,
            hint=lambda e: f'Live event · {e.status}',
            url=lambda e: f'/dashboard/live/{e.pk}/',
        )

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='home_below_grid',
                template='live_commerce/blocks/upcoming_teaser.html',
                priority=40,
            )
        ]

    def contribute_dashboard_cards(self) -> list:
        # A card on the Marketing landing, beside other apps' cards.
        return [
            DashboardCard(
                section='marketing',
                title='Live shopping',
                data='plugins.installed.live_commerce.cards.live_card',
                url='/dashboard/live/',
                cta='Open shows',
                icon='radio',
                order=60,
                capability='marketing.read',
            )
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Live shopping',
                slug='live',
                view='plugins.installed.live_commerce.views.index',
                icon='radio',
                section='marketing',
                order=60,
                url='/dashboard/live/',
            )
        ]
