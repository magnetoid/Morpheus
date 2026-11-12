"""Shipping plugin manifest."""

from __future__ import annotations

import logging

from morpheus.app import Plugin

logger = logging.getLogger('morpheus.shipping')


class ShippingPlugin(Plugin):
    name = 'shipping'
    label = 'Shipping'
    version = '1.0.0'
    description = (
        'Shipping zones and rates (flat fee, weight or order-total tiers, free over an '
        'amount, pickup), live Shippo / EasyPost quotes, and carrier labels for parcels.'
    )
    has_models = True
    requires = ['catalog', 'orders']

    def ready(self) -> None:
        from morpheus import events  # noqa: PLC0415

        self.register_hook(events.DASHBOARD_SEARCH, self.on_dashboard_search)

        self.register_graphql_extension('plugins.installed.shipping.graphql.queries')
        # Tax must run BEFORE shipping (so shipping doesn't get taxed unless
        # we explicitly want that). Tax uses priority 20; we use 30.
        # CART_CALCULATE_TOTAL is deprecated — the canonical event is
        # CART_CALCULATE_BREAKDOWN, fired from OrderService since 2026-04.
        self.register_hook(events.CART_CALCULATE_BREAKDOWN, self.on_cart_breakdown, priority=30)
        # Checkout rate options — the storefront asks via this filter instead
        # of importing shipping.services, so rates vanish on disable.
        self.register_hook(events.CHECKOUT_SHIPPING_RATES, self.on_checkout_rates, priority=10)
        # What this store charges to ship, stated to Google by the app that
        # knows it. The SEO app used to synthesise this from config nothing
        # wrote, so every product page advertised free shipping.
        self.register_hook(events.SEO_JSONLD_GRAPH, self.on_seo_jsonld_graph, priority=50)
        # The order page's "Shipping labels" panel, while a carrier is set up.
        self.register_hook(events.ORDER_DETAIL_PANELS, self.on_order_panels, priority=30)
        self.register_urls(
            'plugins.installed.shipping.urls_dashboard',
            prefix='dashboard/shipping/',
            namespace='shipping_dashboard',
        )

    def on_dashboard_search(self, value, query='', words=None, **kwargs):
        """Shipping zones and rates (by name) in the dashboard's search box."""
        from plugins import dashboard_search as ds
        from plugins.installed.shipping.models import ShippingRate, ShippingZone

        page = '/dashboard/shipping/zones/'
        ds.add(
            value,
            ShippingZone,
            query,
            words,
            fields=('name',),
            section='Shipping',
            kind='shipping_zone',
            icon='map',
            capability='shipping.write',
            label=lambda z: z.name,
            hint=lambda z: 'Shipping zone',
            url=lambda z: f'{page}?edit_kind=zone&edit={z.pk}',
        )
        return ds.add(
            value,
            ShippingRate.objects.select_related('zone'),
            query,
            words,
            fields=('name', 'description'),
            section='Shipping',
            kind='shipping_rate',
            icon='truck',
            capability='shipping.write',
            label=lambda r: r.name,
            hint=lambda r: f'Shipping rate · {r.zone.name}',
            url=lambda r: f'{page}?edit_kind=rate&edit={r.pk}',
        )

    def on_checkout_rates(self, value, cart=None, address=None, **kwargs):
        """CHECKOUT_SHIPPING_RATES: normalized rate options for checkout.

        Returns [{'id','label','amount','currency'}], or None when no zone
        matches — leaving the filter value untouched so checkout falls back
        to free standard delivery (the behaviour stores without configured
        zones already rely on). Raising is fine — the bus isolates it.
        """
        from plugins.installed.shipping.services import list_available_rates  # noqa: PLC0415

        address = address or {}
        rates = list_available_rates(
            cart=cart,
            country=(address.get('country') or '').strip(),
            region=(address.get('region') or address.get('state') or '').strip(),
        )
        normalized = [
            {
                'id': r['rate_id'],
                'label': r['name'],
                'amount': r['amount'].amount,
                'currency': str(r['amount'].currency),
            }
            for r in rates or []
        ]
        return normalized or None

    def on_seo_jsonld_graph(self, value, page=None, request=None, **kwargs):
        from plugins.installed.shipping.seo_graph import on_seo_jsonld_graph  # noqa: PLC0415

        return on_seo_jsonld_graph(value, page=page, request=request, **kwargs)

    def on_order_panels(self, value, order=None, request=None, **kwargs):
        from plugins.installed.shipping.order_panel import order_panel  # noqa: PLC0415

        return order_panel(value, order=order, request=request, **kwargs)

    def on_cart_breakdown(self, value, cart=None, address=None, shipping_rate_id=None, **kwargs):
        if cart is None or not isinstance(value, dict):
            return value
        if not shipping_rate_id:
            return value
        try:
            meta = value.get('meta') or {}
            free_shipping = bool(meta.get('free_shipping'))

            from plugins.installed.shipping.services import quote_rate  # noqa: PLC0415

            country = (address or {}).get('country', '') if address else ''
            region = (address or {}).get('region', '') if address else ''
            quote = quote_rate(cart=cart, rate_id=shipping_rate_id, country=country, region=region)
            if not quote:
                return value

            amount = quote.get('amount')
            if free_shipping:
                from decimal import Decimal  # noqa: PLC0415

                from djmoney.money import Money  # noqa: PLC0415

                currency = str(
                    value.get('currency') or getattr(value.get('subtotal'), 'currency', 'USD')
                )
                amount = Money(Decimal('0'), currency)

            if amount is not None:
                value['shipping'] = amount
                meta['shipping_rate_name'] = quote.get('name') or ''
                value['meta'] = meta

            subtotal = value.get('subtotal')
            shipping = value.get('shipping')
            tax = value.get('tax')
            discount = value.get('discount')
            currency = str(value.get('currency') or getattr(subtotal, 'currency', 'USD'))
            from decimal import Decimal  # noqa: PLC0415

            from djmoney.money import Money  # noqa: PLC0415

            subtotal_a = Decimal(str(getattr(subtotal, 'amount', 0) or 0))
            shipping_a = Decimal(str(getattr(shipping, 'amount', 0) or 0))
            tax_a = Decimal(str(getattr(tax, 'amount', 0) or 0))
            discount_a = Decimal(str(getattr(discount, 'amount', 0) or 0))
            total_a = subtotal_a + shipping_a + tax_a - discount_a
            if total_a < 0:
                total_a = Decimal('0')
            value['total'] = Money(total_a.quantize(Decimal('0.01')), currency)

            return value
        except Exception as e:  # noqa: BLE001
            logger.warning('shipping: on_cart_breakdown failed: %s', e, exc_info=True)
            return value

    def on_cart_total(self, value, cart=None, address=None, shipping_rate_id=None, **kwargs):
        """Add the chosen shipping rate's amount to the cart total."""
        if cart is None or not shipping_rate_id:
            return value
        try:
            from plugins.installed.shipping.services import quote_rate  # noqa: PLC0415

            country = (address or {}).get('country', '') if address else ''
            region = (address or {}).get('region', '') if address else ''
            quote = quote_rate(
                cart=cart,
                rate_id=shipping_rate_id,
                country=country,
                region=region,
            )
            if quote and quote['amount']:
                return value + quote['amount']
            return value
        except Exception as e:  # noqa: BLE001
            logger.warning('shipping: on_cart_total failed: %s', e, exc_info=True)
            return value

    def contribute_agent_tools(self) -> list:
        from plugins.installed.shipping.agent_tools import (  # noqa: PLC0415
            add_flat_rate_tool,
            buy_label_tool,
            list_zones_tool,
            set_rate_tool,
        )

        return [list_zones_tool, add_flat_rate_tool, set_rate_tool, buy_label_tool]

    def contribute_storefront_blocks(self) -> list:
        # "Add X for free shipping" progress bar in the cart summary. Self-hides
        # when no free_over rate is configured. Attacks the top cart-abandonment
        # driver (unexpected shipping cost) and nudges AOV toward the threshold.
        from morpheus import StorefrontBlock  # noqa: PLC0415

        return [
            StorefrontBlock(
                slot='cart_summary_extra',
                template='shipping/blocks/free_progress.html',
                priority=20,
            ),
            # The shipping page's prices: the configured rates, never theme copy.
            StorefrontBlock(
                slot='shipping_rates',
                template='shipping/blocks/rates.html',
                priority=10,
            ),
        ]

    def contribute_dashboard_pages(self) -> list:
        from morpheus import DashboardPage  # noqa: PLC0415

        # Zones + rates are one tabbed "Shipping" area now (the page templates
        # carry the Zones | Rates tab bar), so the settings nav shows a single
        # "Shipping" entry instead of two. Both views/URLs stay intact.
        return [
            DashboardPage(
                label='Shipping zones',
                slug='zones',
                view='plugins.installed.shipping.dashboard.zones',
                icon='truck',
                section='shipping',
                order=10,
                nav='settings',
                url='/dashboard/shipping/zones/',
                hint='Zones, rates and free-shipping rules',
            ),
        ]

    # No SettingsPanel: carrier credentials (Shippo / EasyPost keys + origin)
    # and the tax-on-shipping flag are edited in the "Carriers & options"
    # section of the unified Shipping page (dashboard.zones), which writes them
    # to PluginConfig.config — the same dict services.quote_rate reads. The old
    # panel was a duplicate "Shipping" settings entry alongside the merged page;
    # removed per ADR 0003 (one settings surface per domain, in the owning app).
