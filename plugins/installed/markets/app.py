"""markets plugin manifest."""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin
from morpheus.core import events

logger = logging.getLogger('morpheus.markets')


class MarketsPlugin(Plugin):
    name = 'markets'
    label = 'Markets'
    version = '0.1.0'
    description = (
        'Per-country pricing, currency, and locale. Resolves a market '
        "from the visitor's country (Cloudflare CF-IPCountry header by "
        'default) and applies optional per-product price overrides.'
    )
    has_models = True
    requires = ['catalog']

    def ready(self) -> None:
        from celery.schedules import crontab

        self.register_celery_beat(
            'markets:fetch_exchange_rates',
            {
                'task': 'markets.fetch_exchange_rates',
                'schedule': crontab(hour=15, minute=30),
            },
        )
        self.register_hook(events.HEALTH_CHECKS, self.on_health_checks, priority=60)
        self.register_hook(events.DASHBOARD_SEARCH, self.on_dashboard_search)
        self.register_urls(
            'plugins.installed.markets.urls',
            prefix='dashboard/markets/',
            namespace='markets',
        )

    def get_config_schema(self):
        return {
            'type': 'object',
            'properties': {
                'rate_source': {
                    'type': 'string',
                    'enum': ['ecb', 'manual'],
                    'default': 'ecb',
                    'title': 'Where exchange rates come from',
                    'description': (
                        "'ecb' fetches the European Central Bank's daily rates for the "
                        "currencies your markets use; 'manual' leaves every rate to you. "
                        'A rate you type is never overwritten either way.'
                    ),
                },
            },
        }

    def on_health_checks(self, value, **kwargs):
        """HEALTH_CHECKS: every active market's currency has a current rate."""
        from plugins.installed.markets import rates

        bad = [
            f'{r["currency"]} ({"no rate" if r["rate"] is None else "out of date"})'
            for r in rates.rate_rows()
            if r['stale']
        ]
        value.append(
            {
                'name': 'Exchange rates are current',
                'ok': not bad,
                'detail': ('Markets need a rate for: ' + ', '.join(bad)) if bad else '',
            }
        )
        return value

    def on_dashboard_search(self, value, query='', words=None, **kwargs):
        """Markets (by code, name or currency) in the dashboard's search box."""
        from plugins import dashboard_search as ds
        from plugins.installed.markets.models import Market

        return ds.add(
            value,
            Market,
            query,
            words,
            fields=('code', 'label', 'currency'),
            section='Markets',
            kind='market',
            icon='globe',
            label=lambda m: m.label or m.code,
            hint=lambda m: f'Market · {m.code} · {m.currency}',
            url=lambda m: f'/dashboard/markets/{m.pk}/',
        )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.markets import agent_tools as t  # noqa: PLC0415

        return [
            t.markets_list_tool,
            t.markets_get_tool,
            t.markets_save_tool,
            t.markets_delete_tool,
            t.markets_set_product_price_tool,
            t.markets_set_rate_tool,
            t.markets_refresh_rates_tool,
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                slug='index',
                label='Markets',
                section='general',
                icon='globe',
                view='plugins.installed.markets.views.index',
                order=15,
                nav='settings',
                hint='Countries, currencies and prices per market',
            ),
        ]
