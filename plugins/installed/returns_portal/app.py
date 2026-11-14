"""Returns portal — a *retention* surface, not a transaction.

Extends the canonical return flow (``orders.ReturnRequest`` +
``ReturnService`` in plugins/installed/orders/refunds.py) with
**"exchange or store credit"** as first-class resolutions (exchanges
retain ~70 % of the original order value, per Narvar) and a "we
learned something" feedback box that routes to the CRM plugin's lead
pipeline. The return itself — RMA numbers, state machine, refunds,
store-credit ledger — stays owned by orders; this plugin only attaches
``ReturnResolution`` / ``ReturnFeedback`` rows to it.

Returns are the most emotionally loaded moment in the journey.
The opposite of vibe-coding is a generic UPS label email.
"""

from __future__ import annotations

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock
from plugins.installed.returns_portal.seo_graph import RETURN_FEES


class ReturnsPortalPlugin(Plugin):
    name = 'returns_portal'
    label = 'Returns portal'
    version = '1.0.0'
    description = (
        'Retention layer over the canonical orders return flow: '
        '"exchange or store credit" as first-class resolutions '
        '(exchanges retain ~70 % of the original order value) plus a '
        "feedback box routed to the CRM plugin's lead pipeline."
    )
    has_models = True
    requires = ['orders', 'loyalty_points', 'customers', 'consent']

    def ready(self) -> None:
        from morpheus.core import events  # noqa: PLC0415

        # The return window, stated to Google by the app that owns it. The SEO
        # app used to publish a complete policy — 30 days, free, by mail, US —
        # assembled from constants in its own source, on every store.
        self.register_hook(events.SEO_JSONLD_GRAPH, self.on_seo_jsonld_graph, priority=50)
        # The same window for the pages: a theme says "30-day returns" from
        # `return_window_days`, never from its own copy.
        from plugins.installed.returns_portal.context_processors import (  # noqa: PLC0415
            return_window,
        )

        self.register_context_processor(return_window)

    def on_seo_jsonld_graph(self, value, page=None, request=None, **kwargs):
        from plugins.installed.returns_portal.seo_graph import (  # noqa: PLC0415
            on_seo_jsonld_graph,
        )

        return on_seo_jsonld_graph(value, page=page, request=request, **kwargs)

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='account_summary_extra',
                template='returns_portal/blocks/cta.html',
                priority=10,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Returns portal',
            description='Return window, and who pays for a return, how and for what refund.',
            category='payments',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'return_window_days': {
                    'type': 'integer',
                    'default': 30,
                    'title': 'Return window (days)',
                },
                # The return terms search engines show beside a product. Each is
                # stated only once set: a guess about who pays for a return is
                # the kind that ends in a chargeback (seo_graph.return_policy).
                'return_fees': {
                    'type': 'string',
                    'enum': list(RETURN_FEES),
                    'default': 'not_stated',
                    'title': 'Who pays for a return',
                    'description': (
                        'free: returns cost the customer nothing. customer_pays: the customer '
                        'pays the return postage. fixed_fee: you charge the amount below.'
                    ),
                },
                'return_shipping_fee': {
                    'type': 'number',
                    'default': 0,
                    'title': 'Return shipping fee',
                    'description': 'In your store currency, for "fixed_fee". 0 states none.',
                },
                'return_by_mail': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Customers return by post',
                },
                'return_in_store': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Customers return in a shop',
                },
                'return_at_kiosk': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Customers return at a drop-off point',
                },
                'refund_full': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Refunds the full price',
                },
                'refund_exchange': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Offers an exchange',
                },
                'refund_store_credit': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Offers store credit',
                },
            },
        }
