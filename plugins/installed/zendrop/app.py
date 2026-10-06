"""Zendrop dropshipping — fulfil orders through Zendrop.

Zendrop connects natively to Shopify, Wix, TikTok Shop US and ClickFunnels
only; it offers no CSV order import, and its manual "sample order" form needs
one of those stores connected. Its one programmatic door is an MCP server
(``app.zendrop.com/mcp/v1``) with scoped access tokens, whose tool names are
visible only once connected. This app therefore does three honest things:

* **connects** over MCP and shows the merchant exactly which tools their
  token can reach (discovery, cached an hour) — the foundation for automating
  fulfilment and tracking once Zendrop's tools are known for this account;
* **maps** each variant to its Zendrop product/variant (product-form card);
* **runs the manual loop fast**: an order sheet per paid order (supplier-ready
  address + Zendrop ids per line), "placed in Zendrop" bookkeeping, and shipping
  with a tracking number — one order at a time or from a tracking CSV — the
  platform way (``Order.ship()`` + ``orders.Fulfillment``), so the shopper's
  "on its way" email fires as for any hand-fulfilled order.

Shared supplier machinery lives in ``plugins.dropshipping`` (with the dsers
app). Opt-in per store via ``MORPHEUS_EXTRA_APPS``. Spec:
docs/plans/zendrop-dropshipping.md.
"""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin, SettingsPanel

logger = logging.getLogger('morpheus.zendrop')


class ZendropPlugin(Plugin):
    name = 'zendrop'
    label = 'Zendrop dropshipping'
    version = '1.0.0'
    description = (
        'Fulfil through Zendrop: connect over its MCP server, map variants to Zendrop '
        'products, work paid orders from a copy-ready order sheet, and ship them with '
        'the tracking numbers Zendrop reports.'
    )
    has_models = True
    requires = ['orders', 'catalog']

    def ready(self) -> None:
        from morpheus.core import events  # noqa: PLC0415

        self.register_urls(
            'plugins.installed.zendrop.urls', prefix='dashboard/zendrop/', namespace='zendrop'
        )
        self.register_hook(events.PRODUCT_FORM_CARDS, self.on_product_form_cards, priority=71)
        self.register_hook(events.PRODUCT_FORM_SAVED, self.on_product_form_saved, priority=71)
        self.register_hook(events.ORDER_CANCELLED, self.on_order_cancelled, priority=71)

    # ── dashboard ──────────────────────────────────────────────────────────

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Zendrop',
                slug='orders',
                view='plugins.installed.zendrop.views.dashboard',
                icon='truck',
                section='data',
                order=41,
            )
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Zendrop dropshipping',
            description='The Zendrop access token, where tracking links point, and the processing move.',
            schema=self.get_config_schema(),
            category='apps',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'access_token': {
                    'type': 'string',
                    'format': 'password',
                    'title': 'Zendrop access token',
                    'description': (
                        'Generated in Zendrop for its MCP server (app.zendrop.com/mcp/v1) with the '
                        'orders and catalog scopes. Stored write-only; test it on the Zendrop page.'
                    ),
                },
                'tracking_url_template': {
                    'type': 'string',
                    'default': 'https://t.17track.net/en#nums={tracking}',
                    'title': 'Tracking link template',
                    'description': 'Used for the tracking link on shipped orders; {tracking} is replaced.',
                },
                'mark_processing_when_placed': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Move orders to "processing" when placed in Zendrop',
                    'description': 'A placed order is with the supplier; show it as processing.',
                },
            },
        }

    # ── product form card ──────────────────────────────────────────────────

    @staticmethod
    def _rows_for(product) -> list[dict]:
        from plugins.installed.zendrop.models import ZendropLink

        links = {link.variant_id: link for link in ZendropLink.objects.filter(product=product)}
        variants = list(product.variants.all().order_by('sort_order', 'name'))
        if not variants:
            return [
                {
                    'key': 'product',
                    'label': product.name,
                    'sku': product.sku,
                    'variant_id': None,
                    'link': links.get(None),
                }
            ]
        return [
            {
                'key': f'variant:{v.pk}',
                'label': v.name,
                'sku': v.sku,
                'variant_id': v.pk,
                'link': links.get(v.pk),
            }
            for v in variants
        ]

    def on_product_form_cards(self, value, product=None, **kwargs):
        if product is None or not getattr(product, 'pk', None):
            return value
        value.append(
            {
                'template': 'zendrop/_product_form_card.html',
                'context': {'zendrop_rows': self._rows_for(product)},
                'order': 71,
            }
        )
        return value

    def on_product_form_saved(self, product=None, post=None, **kwargs):
        if product is None or post is None:
            return
        from plugins.installed.zendrop.models import ZendropLink

        for row in self._rows_for(product):
            pid = post.get(f'zendrop_product__{row["key"]}')
            vid = post.get(f'zendrop_variant__{row["key"]}')
            url = post.get(f'zendrop_url__{row["key"]}')
            if pid is None and vid is None and url is None:
                continue  # the card was not on this form
            pid, vid, url = (pid or '').strip(), (vid or '').strip(), (url or '').strip()
            lookup = {'product': product, 'variant_id': row['variant_id']}
            if not pid and not vid and not url:
                ZendropLink.objects.filter(**lookup).delete()
                continue
            ZendropLink.objects.update_or_create(
                **lookup,
                defaults={
                    'zendrop_product_id': pid[:64],
                    'zendrop_variant_id': vid[:64],
                    'product_url': url[:500],
                },
            )

    # ── orders ─────────────────────────────────────────────────────────────

    def on_order_cancelled(self, order=None, **kwargs):
        """An order cancelled after it was placed in Zendrop must be cancelled there too."""
        if order is None:
            return
        from plugins.installed.zendrop.models import ZendropOrder

        ZendropOrder.objects.filter(order=order, status='placed').update(
            status='cancelled',
            note='Cancelled in Morpheus after placing — cancel the Zendrop order.',
        )
