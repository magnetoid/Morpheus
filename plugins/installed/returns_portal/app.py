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

        # The withdrawal function (EU CRD Art. 11a, v0.181.0): its pages, the
        # order email's link, the acknowledgement, and the checklist step and
        # nightly check that say when a store in the EU has it off.
        from plugins.installed.returns_portal import withdrawal  # noqa: PLC0415

        self.register_urls(
            'plugins.installed.returns_portal.urls', prefix='', namespace='returns_portal'
        )
        self.register_hook(events.ORDER_EMAIL_LINKS, withdrawal.on_order_email_links, priority=50)
        self.register_hook(
            events.ORDER_WITHDRAWAL_REQUESTED, withdrawal.on_withdrawal_requested, priority=50
        )
        self.register_hook(events.DASHBOARD_SETUP_STEPS, withdrawal.on_setup_steps, priority=60)
        self.register_hook(events.HEALTH_CHECKS, withdrawal.on_health_checks, priority=60)

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
            StorefrontBlock(
                slot='footer_legal',
                template='returns_portal/blocks/footer_withdraw.html',
                priority=80,
            ),
            StorefrontBlock(
                slot='account_order_actions',
                template='returns_portal/blocks/order_withdraw.html',
                priority=50,
            ),
        ]

    def contribute_email_templates(self) -> list:
        from morpheus.app import EmailTemplateDef  # noqa: PLC0415

        return [
            EmailTemplateDef(
                key='withdrawal_received',
                label='Withdrawal received',
                default_subject='We received your withdrawal from order #{{ order.order_number }}',
                group='Orders',
                description='The acknowledgement a customer gets when they withdraw from the '
                'contract for an order, with the date and time it was received.',
            ),
        ]

    def contribute_agent_tools(self) -> list:
        from plugins.installed.returns_portal.agent_tools import (  # noqa: PLC0415
            list_withdrawals_tool,
            process_withdrawal_tool,
        )

        return [list_withdrawals_tool, process_withdrawal_tool]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Returns portal',
            description=(
                'Return window, who pays for a return, how and for what refund, and the '
                'online withdrawal function.'
            ),
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
                # EU CRD Art. 11a: "Withdraw from contract here" on every order
                # (returns_portal/withdrawal.py). Off until the merchant chooses.
                'withdrawal_function': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Online withdrawal function',
                    'description': (
                        'Shows "Withdraw from contract here" in the order email, on the '
                        "customer's order page and in the footer. EU law asks for it."
                    ),
                },
                'withdrawal_days': {
                    'type': 'integer',
                    'default': 14,
                    'minimum': 14,
                    'title': 'Withdrawal period (days)',
                    'description': (
                        'From delivery for goods, from the order for downloads. The law '
                        'gives 14; you may give more.'
                    ),
                },
            },
        }
