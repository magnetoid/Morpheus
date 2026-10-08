"""DSers dropshipping — fulfil orders through DSers (AliExpress).

DSers connects natively to Shopify, WooCommerce and Wix; for every other
platform it reads two CSV files (product mapping, orders) and hands back the
AliExpress order numbers and tracking numbers. This app is that bridge:

* a product-form card where the merchant links each variant to its AliExpress
  item and SKU (→ the `import_products` file);
* a dashboard page that exports paid, shippable orders as DSers' `import_orders`
  file and imports the tracking export, shipping each order the platform way
  (``Order.ship()`` + ``orders.Fulfillment``, so the shopper's "on its way"
  email and every subscriber fire as usual).

The DSers Open API ("Channel App") is only documented to approved partners;
when the account is approved it slots in behind the same ``OrderSync`` rows
(docs/plans/dsers-dropshipping.md). Opt-in per store via ``MORPHEUS_EXTRA_APPS``.
"""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin, SettingsPanel

logger = logging.getLogger('morpheus.dsers')


class DsersPlugin(Plugin):
    name = 'dsers'
    label = 'DSers dropshipping'
    version = '1.0.0'
    description = (
        'Fulfil through DSers (AliExpress): map variants to supplier items, export paid '
        "orders as DSers' CSV, import the tracking numbers and ship the orders."
    )
    has_models = True
    requires = ['orders', 'catalog']

    def ready(self) -> None:
        from morpheus.core import events  # noqa: PLC0415

        self.register_urls(
            'plugins.installed.dsers.urls', prefix='dashboard/dsers/', namespace='dsers'
        )
        self.register_hook(events.PRODUCT_FORM_CARDS, self.on_product_form_cards, priority=70)
        self.register_hook(events.PRODUCT_FORM_SAVED, self.on_product_form_saved, priority=70)
        self.register_hook(events.ORDER_CANCELLED, self.on_order_cancelled, priority=70)

    # ── dashboard ──────────────────────────────────────────────────────────

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='DSers',
                slug='orders',
                view='plugins.installed.dsers.views.dashboard',
                icon='package',
                section='orders',
                order=60,
                group='Suppliers',
            )
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='DSers dropshipping',
            description='What travels with each order to the supplier, and where tracking links point.',
            schema=self.get_config_schema(),
            category='shipping',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'order_memo': {
                    'type': 'string',
                    'default': '',
                    'title': 'Order memo for suppliers',
                    'description': (
                        'Sent in the "Order memo" column of every exported order — e.g. '
                        '"No invoice or promotional material in the parcel".'
                    ),
                },
                'tracking_url_template': {
                    'type': 'string',
                    'default': 'https://t.17track.net/en#nums={tracking}',
                    'title': 'Tracking link template',
                    'description': 'Used for the tracking link on shipped orders; {tracking} is replaced.',
                },
                'mark_processing_on_export': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Move exported orders to "processing"',
                    'description': 'An exported order is with the supplier; show it as processing.',
                },
            },
        }

    # ── product form card ──────────────────────────────────────────────────

    @staticmethod
    def _rows_for(product) -> list[dict]:
        """One row per variant (or one for the product when it has none)."""
        from plugins.installed.dsers.models import SupplierLink

        links = {link.variant_id: link for link in SupplierLink.objects.filter(product=product)}
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
                'template': 'dsers/_product_form_card.html',
                'context': {'dsers_rows': self._rows_for(product)},
                'order': 70,
            }
        )
        return value

    def on_product_form_saved(self, product=None, post=None, **kwargs):
        if product is None or post is None:
            return
        from plugins.installed.dsers.models import SupplierLink

        for row in self._rows_for(product):
            url = post.get(f'dsers_url__{row["key"]}')
            sku = post.get(f'dsers_sku__{row["key"]}')
            if url is None and sku is None:
                continue  # the card was not on this form
            url, sku = (url or '').strip(), (sku or '').strip()
            lookup = {'product': product, 'variant_id': row['variant_id']}
            if not url and not sku:
                SupplierLink.objects.filter(**lookup).delete()
                continue
            SupplierLink.objects.update_or_create(
                **lookup, defaults={'supplier_url': url[:500], 'supplier_sku': sku[:200]}
            )

    # ── orders ─────────────────────────────────────────────────────────────

    def on_order_cancelled(self, order=None, **kwargs):
        """An order cancelled after it went to DSers must be cancelled there too."""
        if order is None:
            return
        from plugins.installed.dsers.models import OrderSync

        OrderSync.objects.filter(order=order, status='exported').update(
            status='cancelled', note='Cancelled in Morpheus after export — cancel the DSers order.'
        )
