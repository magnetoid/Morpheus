"""Bookvault plugin manifest.

Mirrors the WooCommerce → Bookvault.app integration: live shipping
quotes from BV's API at checkout, auto-resend of paid orders to BV
fulfilment, per-product link tracking, and the BV-hosted bulk product
linker reachable from the admin dashboard.
"""

# Lazy service import in the order hook keeps it load-order-safe. Pre-existing.
# ruff: noqa: PLC0415

from __future__ import annotations

import logging

from django.urls import reverse

from morpheus.app import DashboardPage, Plugin, SettingsPanel
from morpheus.core import events

logger = logging.getLogger('morpheus.bookvault')


class BookvaultPlugin(Plugin):
    name = 'bookvault'
    label = 'Bookvault'
    version = '0.1.0'
    description = (
        'Print-on-demand book fulfilment via Bookvault.app. Live shipping '
        'quotes at checkout, auto-resend paid orders to BV, per-product '
        'link tracking, BV-hosted bulk product linker.'
    )
    has_models = True
    requires = ['catalog', 'orders']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.bookvault.urls',
            prefix='dashboard/apps/bookvault/',
            namespace='bookvault',
        )
        # Auto-send on order paid — matches the WP plugin's "Resend Order
        # To Bookvault" path, but proactive rather than admin-triggered.
        self.register_hook(
            events.ORDER_PAID,
            self.on_order_paid,
            priority=80,
        )
        # Dashboard product surfaces — contributed via the bus so both are
        # disable-safe (ADR 0023). Previously hard-imported by admin_dashboard's
        # products view, which survived disable-while-configured and NoReverseMatch-
        # 500'd the product list when bookvault was boot-disabled (its `{% url %}`
        # target was never registered).
        self.register_hook(
            events.PRODUCT_LIST_COLUMNS,
            self.on_product_list_columns,
            priority=50,
        )
        self.register_hook(
            events.PRODUCT_FORM_CARDS,
            self.on_product_form_cards,
            priority=60,
        )

    def on_order_paid(self, order=None, **kwargs):
        if order is None:
            return
        try:
            from plugins.installed.bookvault.services import send_order

            send_order(order=order)
        except Exception as e:  # noqa: BLE001 — never break checkout if BV is down
            logger.warning(
                'bookvault: auto-send order=%s failed: %s',
                getattr(order, 'id', '?'),
                e,
                exc_info=True,
            )

    def on_product_list_columns(self, value, products=None, **kwargs):
        """Contribute the per-row BV link-status column to the dashboard
        product list — only when BV is configured + authed, so non-BV stores
        see no noise. Annotates each product with ``bv_link_status`` for the
        cell template. (Django templates reject underscore-prefixed attrs,
        hence the public name.)"""
        from plugins.installed.bookvault import services as bv_services

        if not bv_services.is_authenticated():
            return value
        products = products or []
        status = bv_services.bulk_link_status_for([p.id for p in products])
        for p in products:
            p.bv_link_status = status.get(p.id, 'Unlinked')
        value.append(
            {
                'label': 'BV',
                'cell_template': 'bookvault/_product_list_cell.html',
                'order': 50,
                'bulk_action': {
                    'label': 'Send to Bookvault',
                    'icon': 'book-open',
                    'url': reverse('bookvault:bulk_link'),
                    'field': 'ids',  # bulk_link_products reads POST.getlist('ids')
                },
            }
        )
        return value

    def on_product_form_cards(self, value, product=None, **kwargs):
        """Contribute the 'Bookvault fulfilment' card to the product form.
        Pulls every BookvaultProductLink row for this product (one per variant
        + one for the parent) so the card can render the fulfilment-locations +
        linked-status block the WP plugin's ``bvlt_product_meta`` showed."""
        if product is None:
            return value
        from plugins.installed.bookvault import services as bv_services
        from plugins.installed.bookvault.models import (
            BV_LOCATION_CHOICES,
            BookvaultProductLink,
        )

        if not bv_services.is_authenticated():
            return value
        links = list(
            BookvaultProductLink.objects.filter(product=product)
            .select_related('variant')
            .order_by('variant__sort_order', 'variant__name')
        )
        value.append(
            {
                'template': 'bookvault/_product_form_card.html',
                'context': {
                    'bv_links': links,
                    'bv_locations': [
                        {'id': lid, 'name': name} for lid, name in BV_LOCATION_CHOICES
                    ],
                    'bv_bulk_link_url': bv_services.bulk_products_link([str(product.id)]),
                },
                'order': 60,
            }
        )
        return value

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Bookvault',
                slug='overview',
                view='plugins.installed.bookvault.views.overview',
                # Its own page in the Settings/Apps area — NOT lumped under the
                # generic Shipping group (it's a distinct POD-fulfilment app).
                icon='book-open',
                section='shipping',
                order=20,
                nav='settings',
                url='/dashboard/apps/bookvault/',
                hint='Print-on-demand fulfilment: connection and linked products',
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Bookvault',
            description=(
                'Print-on-demand credentials + behaviour. Token is minted '
                "by hitting auth.bookvault.app with this store's URL."
            ),
            schema=self.get_config_schema(),
            # Own integration card, not buried in Shipping settings.
            category='shipping',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'token': {
                    'type': 'string',
                    'format': 'password',  # write-only: never echo the stored credential
                    'default': '',
                    'title': 'BV client token',
                    'description': 'Minted by auth.bookvault.app/api/WooAuth. Click "Connect" on the overview page rather than pasting here.',
                },
                'store_id': {
                    'type': 'string',
                    'default': '',
                    'title': 'BV store ID',
                },
                'authenticated': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Authenticated',
                    'description': 'True once auth.bookvault.app has acknowledged this store.',
                },
                'auto_send_on_paid': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Auto-send orders on payment',
                    'description': 'When on, every ORDER_PAID hook forwards the order to BV fulfilment. Off = admin must Resend manually.',
                },
            },
        }
