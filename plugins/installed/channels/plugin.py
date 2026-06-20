"""Channels — unified sales-channels overview.

A pure aggregator plugin: it owns one dashboard page that collects a status row
from every commerce-channel plugin (google_shopping, meta_commerce, …) via the
CHANNELS_OVERVIEW filter. It imports no sibling plugin and has no models. Disable
it and only the overview page disappears — each channel keeps its own pages.
"""

from __future__ import annotations

from morpheus import DashboardPage, Plugin


class ChannelsPlugin(Plugin):
    name = 'channels'
    label = 'Sales Channels'
    version = '0.1.0'
    description = (
        'Unified overview of every commerce channel (Google, Meta, TikTok, '
        'Pinterest, Microsoft, Amazon, Reddit, Snapchat): connection status, '
        'feed coverage and pixel state in one operator view. Aggregates each '
        "channel's CHANNELS_OVERVIEW contribution — no new credentials."
    )
    has_models = False

    def ready(self) -> None:
        self.register_celery_tasks('plugins.installed.channels.tasks')
        # Refresh cross-channel ads KPIs once a day (cached for the overview).
        self.register_celery_beat(
            'channels:refresh_metrics',
            {'task': 'channels.refresh_metrics', 'schedule': 60 * 60 * 24},
        )

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Sales Channels',
                slug='overview',
                view='plugins.installed.channels.views.overview',
                icon='radio-tower',
                section='marketing',
                order=60,
                nav='main',
            ),
            DashboardPage(
                label='Channel ROAS',
                slug='attribution',
                view='plugins.installed.channels.views.attribution_view',
                icon='trending-up',
                section='marketing',
                order=61,
                nav='main',
            ),
        ]
