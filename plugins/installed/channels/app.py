"""Channels — unified sales-channels overview.

A pure aggregator plugin: it owns one dashboard page that collects a status row
from every commerce-channel plugin (google_shopping, meta_commerce, …) via the
CHANNELS_OVERVIEW filter. It imports no sibling plugin and has no models. Disable
it and only the overview page disappears — each channel keeps its own pages.
"""

from __future__ import annotations

from morpheus.app import DashboardPage, Plugin
from morpheus.core import events

# Channel app name -> the channel key Analytics' journeys use.
_AD_CHANNEL_KEYS = {
    'google_shopping': 'google',
    'meta_commerce': 'meta',
    'tiktok_commerce': 'tiktok',
    'pinterest_commerce': 'pinterest',
    'microsoft_commerce': 'microsoft',
    'amazon_ads': 'amazon',
    'reddit_ads': 'reddit',
    'snapchat_commerce': 'snapchat',
}


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
        # Keep the overview snapshot (and every channel's coverage report) warm
        # so no dashboard request ever walks the catalogue six times over.
        self.register_celery_beat(
            'channels:refresh_overview',
            {'task': 'channels.refresh_overview', 'schedule': 60 * 30},
        )
        # Every ad channel's spend reaches Analytics' Attribution page through here.
        self.register_hook(events.ANALYTICS_AD_SPEND, self._ad_spend, priority=10)

    def _ad_spend(self, value, **_):
        """Answer ANALYTICS_AD_SPEND from the daily metrics cache (no live calls):
        one row per channel that has spent money."""
        from django.core.cache import cache  # noqa: PLC0415

        from plugins.installed.channels.tasks import METRICS_CACHE_KEY  # noqa: PLC0415

        for row in cache.get(METRICS_CACHE_KEY) or []:
            if not isinstance(row, dict):
                continue
            channel = _AD_CHANNEL_KEYS.get(row.get('name'))
            if not channel or not row.get('spend'):
                continue
            value.append(
                {
                    'channel': channel,
                    'spend': row['spend'],
                    'conversions': row.get('conversions'),
                    'platform_revenue': row.get('revenue'),
                    'days': 30,
                }
            )
        return value

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Overview',
                slug='overview',
                view='plugins.installed.channels.views.overview',
                icon='radio-tower',
                section='channels',
                order=10,
                nav='main',
            ),
        ]
