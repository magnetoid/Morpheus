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
            description='Return window, exchange preference, store-credit incentive copy.',
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
            },
        }
