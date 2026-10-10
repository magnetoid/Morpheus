"""AliExpress dropshipping — the AliExpress Open Platform's DS API, connected.

The widest catalogue in dropshipping, reached the official way: the merchant
registers a "Drop Shipping" developer app on openservice.aliexpress.com (AppKey
+ AppSecret, reviewed by AliExpress) and connects their AliExpress buyer
account by OAuth from this app's page. Then:

* **find and import**: search AliExpress' DS catalogue from the dashboard and
  import a product as a draft through the shared importer, prices in the
  store's currency as AliExpress quotes them for this account;
* **place**: a paid order with AliExpress-linked lines is placed on AliExpress
  on its own (``ORDER_PAID``, plus a 30-minute sweep), one AliExpress order per
  seller, with ``out_order_id`` as the idempotency key;
* **pay**: in the AliExpress account (the page shows each order's deadline), or
  automatically through PayPal for accounts AliExpress whitelisted for it;
* **track**: the sweep reads each order's status and tracking and ships the
  store order the platform way once every AliExpress order has a number.

There is no cancel method: a store cancellation is flagged for a manual cancel.
Opt-in per store via ``MORPHEUS_EXTRA_APPS``. Contract digest:
docs/plans/cj-aliexpress-dropshipping.md.
"""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin, SettingsPanel

logger = logging.getLogger('morpheus.aliexpress')


class AliExpressPlugin(Plugin):
    name = 'aliexpress'
    label = 'AliExpress dropshipping'
    version = '1.0.0'
    description = (
        'Dropship from AliExpress through its official DS API: connect the AliExpress account, '
        'import products, place paid orders automatically and ship them with the tracking '
        'AliExpress reports.'
    )
    has_models = True
    requires = ['orders', 'catalog']

    def ready(self) -> None:
        from morpheus.core import events  # noqa: PLC0415

        self.register_urls(
            'plugins.installed.aliexpress.urls',
            prefix='dashboard/aliexpress/',
            namespace='aliexpress',
        )
        self.register_celery_tasks('plugins.installed.aliexpress.tasks')
        self.register_celery_beat(
            'aliexpress:sync', {'task': 'aliexpress.sync', 'schedule': 60 * 30}
        )
        self.register_hook(events.PRODUCT_FORM_CARDS, self.on_product_form_cards, priority=73)
        self.register_hook(events.PRODUCT_FORM_SAVED, self.on_product_form_saved, priority=73)
        self.register_hook(events.ORDER_PAID, self.on_order_paid, priority=73)
        self.register_hook(events.ORDER_CANCELLED, self.on_order_cancelled, priority=73)

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='AliExpress',
                slug='orders',
                view='plugins.installed.aliexpress.views.dashboard',
                icon='shopping-bag',
                section='orders',
                order=63,
                group='Suppliers',
            )
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='AliExpress dropshipping',
            description='The AliExpress developer app, how orders are placed and paid, and how imported products are priced.',
            schema=self.get_config_schema(),
            category='shipping',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'app_key': {
                    'type': 'string',
                    'title': 'AliExpress AppKey',
                    'description': 'From your "Drop Shipping" app on openservice.aliexpress.com → App Management.',
                },
                'app_secret': {
                    'type': 'string',
                    'format': 'password',
                    'title': 'AliExpress AppSecret',
                    'description': 'Stored write-only.',
                },
                'ship_to_country': {
                    'type': 'string',
                    'default': 'US',
                    'title': 'Main destination country',
                    'description': 'Two-letter code. Search results and imported prices are quoted for shipping here.',
                },
                'logistics_service': {
                    'type': 'string',
                    'default': '',
                    'title': 'Delivery service',
                    'description': 'An AliExpress delivery code (e.g. CAINIAO_STANDARD). Blank: the cheapest offered for each order.',
                },
                'auto_forward': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Place paid orders on AliExpress automatically',
                },
                'auto_pay': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Pay through PayPal automatically',
                    'description': 'Only for accounts AliExpress has whitelisted for API payment (ask ds-api@aliexpress.com). Off: pay each order in your AliExpress account.',
                },
                'price_markup': {
                    'type': 'number',
                    'default': 2.0,
                    'title': 'Price markup for imported products',
                    'description': 'Sale price = AliExpress cost × this.',
                },
                'charm_pricing': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'End imported prices in .99',
                },
                'tracking_url_template': {
                    'type': 'string',
                    'default': 'https://t.17track.net/en#nums={tracking}',
                    'title': 'Tracking link template',
                    'description': '{tracking} is replaced.',
                },
                'mark_processing_when_sent': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Move orders to "processing" when placed on AliExpress',
                },
            },
        }

    @staticmethod
    def _rows_for(product) -> list[dict]:
        from plugins.installed.aliexpress.models import AELink  # noqa: PLC0415

        links = {link.variant_id: link for link in AELink.objects.filter(product=product)}
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
                'template': 'aliexpress/_product_form_card.html',
                'context': {'ae_rows': self._rows_for(product)},
                'order': 73,
            }
        )
        return value

    def on_product_form_saved(self, product=None, post=None, **kwargs):
        if product is None or post is None:
            return
        from plugins.installed.aliexpress.models import AELink  # noqa: PLC0415

        for row in self._rows_for(product):
            pid = post.get(f'ae_product__{row["key"]}')
            attr = post.get(f'ae_sku_attr__{row["key"]}')
            sku_id = post.get(f'ae_sku_id__{row["key"]}')
            if pid is None and attr is None and sku_id is None:
                continue  # the card was not on this form
            pid, attr, sku_id = (pid or '').strip(), (attr or '').strip(), (sku_id or '').strip()
            lookup = {'product': product, 'variant_id': row['variant_id']}
            if not pid.isdigit():
                AELink.objects.filter(**lookup).delete()
                continue
            AELink.objects.update_or_create(
                **lookup,
                defaults={
                    'ae_product_id': pid[:32],
                    'sku_attr': attr[:500],
                    'ae_sku_id': sku_id[:40],
                },
            )

    def on_order_paid(self, order=None, **kwargs):
        if order is None or not self.get_config_value('auto_forward', True):
            return
        try:
            from plugins.installed.aliexpress.tasks import forward  # noqa: PLC0415

            forward.delay(str(order.pk))
        except Exception:  # noqa: BLE001 — the 30-minute sweep picks it up
            logger.warning(
                'aliexpress: could not queue order %s', getattr(order, 'pk', '?'), exc_info=True
            )

    def on_order_cancelled(self, order=None, **kwargs):
        if order is None:
            return
        from plugins.installed.aliexpress.models import AEOrder  # noqa: PLC0415
        from plugins.installed.aliexpress.services.orders import cancel  # noqa: PLC0415

        record = AEOrder.objects.filter(order=order).first()
        if record is not None:
            cancel(record)
