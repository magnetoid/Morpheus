"""CJdropshipping — a supplier with an open API and warehouses worldwide.

CJ's Open API 2.0 is open to any CJ account (an API key from the account's API
page, no partner review), so this app automates the whole loop:

* **find and import**: search CJ's catalogue from the dashboard and import a
  product as a draft — photos, one variant per CJ SKU, price from the cost by
  the markup — through the shared importer (``plugins.dropshipping.importer``);
* **send**: a paid order with CJ-linked lines becomes a CJ order on its own
  (``ORDER_PAID``, plus a sweep every 20 minutes for anything missed), paid
  from the CJ balance or left for the merchant to pay;
* **track**: CJ's signed webhooks (and the same sweep) bring the status and the
  tracking number back, and the order ships the platform way
  (``Order.ship()`` + ``orders.Fulfillment``), so the shopper's email fires once;
* **map by hand**: a product-form card links any existing product to a CJ vid.

Opt-in per store via ``MORPHEUS_EXTRA_APPS``. Contract digest and decisions:
docs/plans/cj-aliexpress-dropshipping.md.
"""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin, SettingsPanel

logger = logging.getLogger('morpheus.cjdropshipping')


class CJDropshippingPlugin(Plugin):
    name = 'cjdropshipping'
    label = 'CJdropshipping'
    version = '1.0.0'
    description = (
        'Dropship worldwide through CJdropshipping: import products from its catalogue, '
        'send paid orders automatically, pay them from the CJ balance and ship them with '
        'the tracking CJ reports.'
    )
    has_models = True
    requires = ['orders', 'catalog']

    def ready(self) -> None:
        from morpheus.core import events  # noqa: PLC0415

        self.register_urls(
            'plugins.installed.cjdropshipping.urls',
            prefix='dashboard/cj/',
            namespace='cjdropshipping',
        )
        # CJ's callback: outside the language tree, like every machine endpoint.
        self.register_urls(
            'plugins.installed.cjdropshipping.webhook_urls',
            prefix='cj/',
            namespace='cjdropshipping_webhook',
            surface='chrome',
        )
        self.register_celery_tasks('plugins.installed.cjdropshipping.tasks')
        self.register_celery_beat(
            'cjdropshipping:sync', {'task': 'cjdropshipping.sync', 'schedule': 60 * 20}
        )
        self.register_hook(events.PRODUCT_FORM_CARDS, self.on_product_form_cards, priority=72)
        self.register_hook(events.PRODUCT_FORM_SAVED, self.on_product_form_saved, priority=72)
        self.register_hook(events.ORDER_PAID, self.on_order_paid, priority=72)
        self.register_hook(events.ORDER_CANCELLED, self.on_order_cancelled, priority=72)

    # ── dashboard ──────────────────────────────────────────────────────────

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='CJdropshipping',
                slug='cj',
                view='plugins.installed.cjdropshipping.views.dashboard',
                icon='globe',
                section='orders',
                order=62,
                group='Suppliers',
            )
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='CJdropshipping',
            description='The CJ API key, how orders are sent and paid, and how imported products are priced.',
            schema=self.get_config_schema(),
            category='shipping',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'api_key': {
                    'type': 'string',
                    'format': 'password',
                    'title': 'CJ API key',
                    'description': (
                        'From cjdropshipping.com → My CJ → Authorization → API (install the API app, '
                        'then "Add API", type "API Key"). Stored write-only.'
                    ),
                },
                'auto_forward': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Send paid orders to CJ automatically',
                    'description': 'Off: paid orders wait on the CJdropshipping page for "Send to CJ".',
                },
                'auto_pay': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Pay CJ orders from the CJ balance straight away',
                    'description': 'Off: the order is created in CJ and waits for "Pay" on the CJdropshipping page (or in CJ).',
                },
                'logistic_name': {
                    'type': 'string',
                    'default': '',
                    'title': 'Shipping method',
                    'description': 'A CJ method name such as "CJPacket Ordinary". Blank: the cheapest CJ offers for each order.',
                },
                'ship_from_country': {
                    'type': 'string',
                    'default': 'CN',
                    'title': 'Ship from (CJ warehouse country)',
                    'description': 'Two-letter code: CN, US, GB, DE … — where CJ sends your orders from.',
                },
                'price_markup': {
                    'type': 'number',
                    'default': 2.0,
                    'title': 'Price markup for imported products',
                    'description': 'Sale price = CJ cost × this. 2.0 doubles the cost.',
                },
                'charm_pricing': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'End imported prices in .99',
                },
                'usd_to_store_rate': {
                    'type': 'number',
                    'default': 1.0,
                    'title': 'USD → store currency rate',
                    'description': 'CJ prices are in US dollars. Leave 1 when the store sells in USD.',
                },
                'tracking_url_template': {
                    'type': 'string',
                    'default': 'https://t.17track.net/en#nums={tracking}',
                    'title': 'Tracking link template',
                    'description': 'Used when CJ sends no tracking link; {tracking} is replaced.',
                },
                'mark_processing_when_sent': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Move orders to "processing" when sent to CJ',
                },
            },
        }

    # ── product form card ──────────────────────────────────────────────────

    @staticmethod
    def _rows_for(product) -> list[dict]:
        from plugins.installed.cjdropshipping.models import CJLink  # noqa: PLC0415

        links = {link.variant_id: link for link in CJLink.objects.filter(product=product)}
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
                'template': 'cjdropshipping/_product_form_card.html',
                'context': {'cj_rows': self._rows_for(product)},
                'order': 72,
            }
        )
        return value

    def on_product_form_saved(self, product=None, post=None, **kwargs):
        if product is None or post is None:
            return
        from plugins.installed.cjdropshipping.models import CJLink  # noqa: PLC0415

        for row in self._rows_for(product):
            vid = post.get(f'cj_vid__{row["key"]}')
            pid = post.get(f'cj_pid__{row["key"]}')
            if vid is None and pid is None:
                continue  # the card was not on this form
            vid, pid = (vid or '').strip(), (pid or '').strip()
            lookup = {'product': product, 'variant_id': row['variant_id']}
            if not vid:
                CJLink.objects.filter(**lookup).delete()
                continue
            CJLink.objects.update_or_create(
                **lookup, defaults={'cj_variant_id': vid[:64], 'cj_product_id': pid[:64]}
            )

    # ── orders ─────────────────────────────────────────────────────────────

    def on_order_paid(self, order=None, **kwargs):
        """Send the order to CJ in the background when it has CJ-linked lines."""
        if order is None or not self.get_config_value('auto_forward', True):
            return
        try:
            from plugins.installed.cjdropshipping.tasks import forward  # noqa: PLC0415

            forward.delay(str(order.pk))
        except Exception:  # noqa: BLE001 — the 20-minute sweep picks it up
            logger.warning(
                'cjdropshipping: could not queue order %s', getattr(order, 'pk', '?'), exc_info=True
            )

    def on_order_cancelled(self, order=None, **kwargs):
        if order is None:
            return
        from plugins.installed.cjdropshipping.models import CJOrder  # noqa: PLC0415
        from plugins.installed.cjdropshipping.services.orders import cancel  # noqa: PLC0415

        record = CJOrder.objects.filter(order=order).first()
        if record is not None:
            cancel(record)
