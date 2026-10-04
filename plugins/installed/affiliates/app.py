"""Affiliates plugin manifest."""

# ruff: noqa: PLC0415
# Inline imports throughout keep optional cross-plugin imports lazy and the
# manifest importable before the app registry is ready.
from __future__ import annotations

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock
from morpheus.core import events


class AffiliatesPlugin(Plugin):
    name = 'affiliates'
    label = 'Affiliate Platform'
    version = '0.2.0'
    description = (
        'Affiliate links, attribution, conversions, payouts. Commission tiers, '
        'per-category overrides, auto-approve. Embeddable shop widgets '
        '(iframe + JS snippet).'
    )
    has_models = True
    requires = ['orders', 'customers', 'catalog']

    def ready(self) -> None:
        # GDPR slice: contribute this plugin's data to the export/erasure.
        from plugins.installed.affiliates import gdpr  # noqa: PLC0415

        self.register_hook(events.CUSTOMER_DATA_EXPORT, gdpr.on_customer_export, priority=60)
        self.register_graphql_extension('plugins.installed.affiliates.graphql.queries')
        self.register_urls('plugins.installed.affiliates.urls', prefix='', namespace='affiliates')
        self.register_urls(
            'plugins.installed.affiliates.urls_dashboard',
            prefix='dashboard/affiliates/',
            namespace='affiliates_dashboard',
        )
        self.register_hook(events.ORDER_PLACED, self.on_order_placed, priority=70)
        # Refund clawback. ORDER_CANCELLED fires today; PAYMENT_REFUNDED
        # is defined but not yet emitted by the orders plugin — wire it
        # here too so we plug in automatically when orders starts
        # firing it.
        self.register_hook(events.ORDER_CANCELLED, self.on_order_refunded, priority=70)
        if hasattr(events, 'PAYMENT_REFUNDED'):
            self.register_hook(events.PAYMENT_REFUNDED, self.on_order_refunded, priority=70)
        # Contribute the Affiliate on/off panel to the dashboard customer-detail
        # page. Only registered while affiliates is enabled, so disabling the
        # plugin removes the toggle (modular-os contract).
        from plugins.installed.affiliates.customer_panel import affiliate_panel

        self.register_hook(events.CUSTOMER_DETAIL_PANELS, affiliate_panel, priority=40)

    def contribute_storefront_blocks(self) -> list:
        # Account-page tile linking the signed-in affiliate to their
        # dashboard (/affiliates/me/). Renders only when the user actually
        # has an Affiliate row; disabling the plugin removes the tile.
        return [
            StorefrontBlock(
                slot='account_nav',
                template='affiliates/blocks/account_tile.html',
                priority=40,
                context_keys=['request'],
            ),
        ]

    def on_order_placed(self, order, **kwargs):
        """Attribute an affiliate to a freshly-placed order.

        Two attribution signals (in priority):
          1. ``shipping_address.affiliate_code`` — set by the
             storefront when the ``morph_aff`` cookie was present.
          2. ``order.source`` of the form ``affiliate:<code>``.
          3. The order's coupon code (Phase A1.5) — if it matches
             an ``AffiliateLink.coupon_code`` we attribute even
             without a click. This is how influencer shout-outs
             work in 2026.
        """
        code = ''
        if getattr(order, 'shipping_address', None):
            code = (
                order.shipping_address.get('affiliate_code', '')
                if isinstance(order.shipping_address, dict)
                else ''
            )
        if not code and getattr(order, 'source', '').startswith('affiliate:'):
            code = order.source.split(':', 1)[1]

        # Coupon attribution fallback. Pull from order.coupon_code or
        # order.metadata.coupon_code depending on what the cart wrote.
        coupon = (getattr(order, 'coupon_code', '') or '').strip()
        if not coupon and isinstance(getattr(order, 'metadata', None), dict):
            coupon = (order.metadata.get('coupon_code') or '').strip()

        if not code and not coupon:
            return
        from plugins.installed.affiliates.services import attribute_order

        attribute_order(order=order, affiliate_code=code, coupon_code=coupon)

    def on_order_refunded(self, order, **kwargs):
        """Reverse any affiliate conversion attached to a refunded
        order. See ``services.clawback_on_refund`` for the policy."""
        from plugins.installed.affiliates.services import clawback_on_refund

        try:
            clawback_on_refund(order=order)
        except Exception as exc:  # noqa: BLE001 — never block refund processing
            import logging

            logging.getLogger('morpheus.affiliates').warning(
                'clawback failed for order %s: %s',
                getattr(order, 'pk', '?'),
                exc,
            )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.affiliates.agent_tools import (
            create_affiliate_tool,
            list_affiliates_tool,
            mark_payout_paid_tool,
            pending_payouts_tool,
        )

        return [
            list_affiliates_tool,
            pending_payouts_tool,
            mark_payout_paid_tool,
            create_affiliate_tool,
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Affiliates',
            description='Default program rules and payout policy. New AffiliateProgram rows inherit these defaults.',
            schema=self.get_config_schema(),
            category='marketing',
        )

    def contribute_email_templates(self) -> list:
        from morpheus.app import EmailTemplateDef

        return [
            EmailTemplateDef(
                key='affiliate_approved',
                label='Affiliate approved',
                default_subject='You’re approved — welcome to the affiliate programme',
                group='Affiliates',
                description='Sent to an affiliate when you approve their application.',
            ),
        ]

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'default_commission_percent': {
                    'type': 'number',
                    'title': 'Default commission %',
                    'description': 'Percentage of order subtotal an affiliate earns by default.',
                    'default': 10,
                },
                'cookie_window_days': {
                    'type': 'integer',
                    'title': 'Cookie window (days)',
                    'description': 'How long an affiliate click remains attributable. 30 is industry standard.',
                    'default': 30,
                },
                'min_payout_threshold': {
                    'type': 'number',
                    'title': 'Minimum payout threshold',
                    'description': 'Affiliates must accrue at least this much before a payout is generated.',
                    'default': 25,
                },
            },
        }

    def contribute_dashboard_pages(self) -> list:
        # nav='main': the sidebar group is rendered by the contributed-
        # sections loop (section='growth', labelled 'Affiliates') — the old
        # hardcoded base.html block is gone, so disable removes everything.
        from morpheus.app import DashboardPage

        return [
            DashboardPage(
                label='Affiliates',
                slug='list',
                view='plugins.installed.affiliates.dashboard.affiliates_list',
                icon='link',
                section='growth',
                order=10,
                nav='main',
            ),
            DashboardPage(
                label='Programs',
                slug='programs',
                view='plugins.installed.affiliates.dashboard.programs_list',
                icon='layers',
                section='growth',
                order=15,
                nav='main',
            ),
            DashboardPage(
                label='Links',
                slug='links',
                view='plugins.installed.affiliates.dashboard.links_list',
                icon='link-2',
                section='growth',
                order=17,
                nav='main',
            ),
            DashboardPage(
                label='Creatives',
                slug='creatives',
                view='plugins.installed.affiliates.dashboard.creatives_list',
                icon='image',
                section='growth',
                order=17,
                nav='main',
            ),
            DashboardPage(
                label='Conversions',
                slug='conversions',
                view='plugins.installed.affiliates.dashboard.conversions_list',
                icon='trending-up',
                section='growth',
                order=18,
                nav='main',
            ),
            DashboardPage(
                label='Payouts',
                slug='payouts',
                view='plugins.installed.affiliates.dashboard.payouts_list',
                icon='wallet',
                section='growth',
                order=20,
                nav='main',
            ),
            DashboardPage(
                label='Analytics',
                slug='analytics',
                view='plugins.installed.affiliates.dashboard.analytics',
                icon='bar-chart-3',
                section='growth',
                order=25,
                nav='main',
            ),
        ]
