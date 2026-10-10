"""ChatGPT Shopping feed — the door into ChatGPT for a store that is not on Shopify.

OpenAI retired Instant Checkout in March 2026; what remains is discovery, and a
merchant on a custom stack gets in by applying at chatgpt.com/merchants and
sharing a product feed in OpenAI's feed specification (JSONL or CSV; refreshed
as often as every 15 minutes; optionally pushed over HTTPS to an endpoint
OpenAI allow-lists). Required per row: ``item_id``, ``title``, ``description``,
``url``, ``brand``, ``seller_name``, ``image_url``, ``availability``,
``price``; ``is_eligible_search`` (default true) and ``is_eligible_checkout``
(needs ``seller_privacy_policy`` + ``seller_tos``); variants via ``group_id``
and ``variant_dict``; returns via ``accepts_returns``,
``return_deadline_in_days`` and ``return_policy``.

The rows come from the shared channel field resolver (``plugins/feed_mapping.py``,
the one every ad/commerce feed uses — ``mapping.py`` here is the thin adapter,
like tiktok_commerce's), reshaped to OpenAI's names. Perplexity's merchant
program takes the same data.
"""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin, SettingsPanel
from morpheus.core import events

logger = logging.getLogger('morpheus.openai_shopping')

FEED_PATH = '/feeds/openai-products.jsonl'


class OpenAIShoppingPlugin(Plugin):
    name = 'openai_shopping'
    label = 'ChatGPT Shopping'
    version = '0.1.0'
    description = (
        "Product feed in OpenAI's feed specification (JSONL) for ChatGPT shopping "
        'and the Perplexity merchant program — served at /feeds/openai-products.jsonl '
        'and, when an allow-listed endpoint is configured, pushed to it every six hours. '
        'Reuses the shared channel field resolver (price, image, identifiers, '
        'availability) with the seller, country and policy fields OpenAI requires.'
    )
    has_models = False
    requires = ['catalog']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.openai_shopping.urls', prefix='', namespace='openai_shopping'
        )
        self.register_celery_tasks('plugins.installed.openai_shopping.tasks')
        self.register_celery_beat(
            'openai_shopping:push_feed',
            {'task': 'openai_shopping.push_feed', 'schedule': 60 * 60 * 6},
        )
        self.register_hook(events.CHANNELS_OVERVIEW, self._channels_row, priority=12)

    def _channels_row(self, value, **_):
        row = {
            'name': 'openai_shopping',
            'label': 'ChatGPT',
            'icon': 'message-circle',
            'connected': False,
            'pixel': None,
            'has_feed': True,
            'eligible': None,
            'total': None,
            'coverage_pct': None,
            'dashboard_url': '/dashboard/apps/openai_shopping/overview/',
        }
        try:
            from plugins.installed.openai_shopping.feed import coverage  # noqa: PLC0415

            rep = coverage()
            row.update(
                connected=rep['push_configured'],
                eligible=rep['in_feed'],
                total=rep['active'],
                coverage_pct=rep['coverage_pct'],
            )
        except Exception as e:  # noqa: BLE001
            logger.debug('openai_shopping: channels row failed: %s', e)
        value.append(row)
        return value

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='ChatGPT Shopping',
                slug='overview',
                view='plugins.installed.openai_shopping.views.dashboard',
                icon='message-circle',
                section='channels',
                order=22,
                nav='main',
                group='ChatGPT',
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='ChatGPT Shopping feed',
            description=(
                "OpenAI's product feed: the seller and policy fields every row carries, "
                'which countries the products are offered in, and the optional endpoint '
                'the feed is pushed to once OpenAI allow-lists it.'
            ),
            schema=self.get_config_schema(),
            category='channels',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'enabled': {'type': 'boolean', 'title': 'Feed enabled', 'default': True},
                'seller_name': {
                    'type': 'string',
                    'title': 'Seller name',
                    'description': 'Shown in ChatGPT as the seller. Blank uses the store name.',
                    'default': '',
                },
                'store_country': {
                    'type': 'string',
                    'title': 'Store country (ISO code)',
                    'description': 'Blank uses the store country from Settings → General.',
                    'default': '',
                },
                'target_countries': {
                    'type': 'string',
                    'title': 'Target countries (ISO codes, comma-separated)',
                    'description': 'Where the products may be bought. Blank uses the store country.',
                    'default': '',
                },
                'seller_privacy_policy': {
                    'type': 'string',
                    'title': 'Privacy policy URL',
                    'description': 'Required for checkout eligibility. Blank uses /p/privacy/.',
                    'default': '',
                },
                'seller_tos': {
                    'type': 'string',
                    'title': 'Terms of service URL',
                    'description': 'Required for checkout eligibility. Blank uses /p/terms/.',
                    'default': '',
                },
                'checkout_eligible': {
                    'type': 'boolean',
                    'title': 'Mark products eligible for checkout inside ChatGPT',
                    'description': 'Needs the agentic checkout (ACP) to be live as well.',
                    'default': False,
                },
                'accepts_returns': {'type': 'boolean', 'title': 'Accepts returns', 'default': True},
                'return_deadline_days': {
                    'type': 'integer',
                    'title': 'Return deadline (days)',
                    'default': 30,
                },
                'return_policy_url': {
                    'type': 'string',
                    'title': 'Return policy URL',
                    'description': 'Blank uses /returns/.',
                    'default': '',
                },
                'default_brand': {
                    'type': 'string',
                    'title': 'Default brand',
                    'description': 'Used when a product has no brand of its own. Blank uses the seller name.',
                    'default': '',
                },
                'default_condition': {
                    'type': 'string',
                    'title': 'Default condition',
                    'enum': ['new', 'refurbished', 'used'],
                    'default': 'new',
                },
                'include_out_of_stock': {
                    'type': 'boolean',
                    'title': 'Include out-of-stock products',
                    'default': True,
                },
                'push_endpoint': {
                    'type': 'string',
                    'title': 'Push endpoint URL',
                    'description': 'The HTTPS endpoint OpenAI allow-listed for this store. Blank = no push; the feed is still served at /feeds/openai-products.jsonl.',
                    'default': '',
                },
                'push_token': {
                    'type': 'string',
                    'title': 'Push bearer token',
                    'format': 'password',
                    'default': '',
                },
            },
        }
