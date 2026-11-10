from celery.schedules import crontab

from morpheus.app import DashboardCard, Plugin
from morpheus.core import events


class InventoryPlugin(Plugin):
    name = 'inventory'
    label = 'Inventory'
    version = '1.0.0'
    description = 'Warehouses, stock levels, movements, low-stock alerts; atomic reservations.'
    has_models = True
    requires = ['catalog']

    def ready(self):
        self.register_urls(
            'plugins.installed.inventory.urls',
            prefix='',
            namespace='inventory',
        )
        self.register_urls(
            'plugins.installed.inventory.urls_dashboard',
            prefix='dashboard/inventory/',
            namespace='inventory_dashboard',
        )
        self.register_graphql_extension('plugins.installed.inventory.graphql.queries')
        self.register_graphql_extension('plugins.installed.inventory.graphql.mutations')
        # Fail-closed stock gate: reserve inside create_from_cart's transaction
        # via a raise_errors filter so a short-stock order actually rolls back
        # (the plain order.placed bus swallows the InsufficientStockError → the
        # old subscription could never block an oversell).
        self.register_hook(events.ORDER_RESERVE_STOCK, self.reserve_stock_filter, priority=5)
        # Dashboard-home low-stock tile.
        self.register_hook(events.DASHBOARD_HOME_PANELS, self.on_dashboard_panels, priority=50)
        # Stock for surfaces that show it without owning it (the vendor portal).
        self.register_hook(events.PRODUCT_STOCK_SUMMARY, self.on_stock_summary, priority=50)
        self.register_hook(events.VARIANT_STOCK_SUMMARY, self.on_variant_stock_summary, priority=50)
        # The "Stock" card on the product form (stock_card.py).
        self.register_hook(events.PRODUCT_FORM_CARDS, self.on_product_form_cards, priority=45)
        self.register_hook(events.PRODUCT_FORM_SAVED, self.on_product_form_saved, priority=45)
        # A CSV import's `stock` column (importers fire it, this app answers).
        self.register_hook(events.INVENTORY_SET_STOCK, self.on_set_stock, priority=50)
        self.register_hook(events.DASHBOARD_SEARCH, self.on_dashboard_search, priority=50)
        self.register_hook('order.paid', self.on_order_paid, priority=5)
        self.register_hook('order.cancelled', self.on_order_cancelled, priority=5)
        self.register_hook('return.refunded', self.on_return_refunded, priority=5)
        self.register_celery_tasks('plugins.installed.inventory.tasks')

        # "Email me when it's back": a stock write that leaves sellable units
        # enqueues the product's waiting subscribers (back_in_stock.py).
        from django.db.models.signals import post_save  # noqa: PLC0415

        from plugins.installed.inventory.back_in_stock import (  # noqa: PLC0415
            on_stock_level_saved,
        )
        from plugins.installed.inventory.models import StockLevel  # noqa: PLC0415

        post_save.connect(
            on_stock_level_saved,
            sender=StockLevel,
            dispatch_uid='inventory.back_in_stock',
            weak=False,
        )

        # Beat schedules: apply price schedules every 5 min. (Abandoned-cart
        # detection is owned solely by the cart_abandonment plugin — inventory's
        # duplicate, un-stamped detector was removed; see tasks.py.)
        self.register_celery_beat(
            'inventory:apply_price_schedules',
            {
                'task': 'inventory.apply_price_schedules',
                'schedule': 60 * 5,
            },
        )
        # Redis fast-path: drift reconciliation every 5 min. No-ops if
        # no `stock:*` keys exist in Redis (i.e. fast-path not in use).
        self.register_celery_beat(
            'inventory:reconcile_redis_stock',
            {
                'task': 'inventory.reconcile_redis_stock',
                'schedule': 60 * 5,
            },
        )
        # Daily predictive stockout forecast → dedup'd staff alerts.
        self.register_celery_beat(
            'inventory:run_stockout_forecast',
            {
                'task': 'inventory.run_stockout_forecast',
                'schedule': crontab(hour=6, minute=0),  # 06:00 UTC daily
            },
        )

    def on_product_form_cards(self, value, product=None, request=None, **kwargs):
        """The "Stock" card, on a saved product that has stock to count."""
        from plugins.installed.inventory import stock_card  # noqa: PLC0415

        context = stock_card.card(product, user=getattr(request, 'user', None))
        if context is not None:
            value.append(
                {
                    'template': 'inventory/blocks/product_stock_card.html',
                    'context': context,
                    'order': 45,
                }
            )
        return value

    def on_product_form_saved(self, product=None, post=None, user=None, **kwargs):
        from plugins.installed.inventory import stock_card  # noqa: PLC0415

        stock_card.save(product, post, user=user)

    def on_set_stock(self, value=False, product=None, quantity=None, warehouse_code='', **kwargs):
        """INVENTORY_SET_STOCK: ``quantity`` units of ``product`` (sold in one form)
        in the warehouse with ``warehouse_code``, else the default one. True when
        it was written; a product with several variants is left as it was."""
        from plugins.installed.catalog.variants import ensure_stock_variant  # noqa: PLC0415
        from plugins.installed.inventory.models import Warehouse  # noqa: PLC0415
        from plugins.installed.inventory.services import (  # noqa: PLC0415
            InventoryService,
            default_warehouse,
        )

        if product is None or quantity is None:
            return value
        variant = ensure_stock_variant(product)
        code = (warehouse_code or '').strip()
        warehouse = (
            (
                Warehouse.objects.filter(code__iexact=code).first()
                or Warehouse.objects.filter(name__iexact=code).first()
            )
            if code
            else default_warehouse(create=True)
        )
        if variant is None or warehouse is None:
            return value
        InventoryService.set_quantity(
            variant, warehouse, int(quantity), reason=kwargs.get('reason') or 'Imported'
        )
        return True

    def on_dashboard_search(self, value, query='', words=None, **kwargs):
        """Warehouses (by name or code) in the dashboard's search box."""
        from plugins import dashboard_search as ds  # noqa: PLC0415
        from plugins.installed.inventory.models import Warehouse  # noqa: PLC0415

        return ds.add(
            value,
            Warehouse,
            query,
            words,
            fields=('name', 'code'),
            section='Inventory',
            kind='warehouse',
            icon='package',
            capability='inventory.write',
            label=lambda w: w.name,
            hint=lambda w: f'Warehouse · {w.code}' + ('' if w.is_active else ' · off'),
            url=lambda w: f'/dashboard/inventory/warehouses/?edit={w.pk}',
        )

    def on_dashboard_panels(self, value, date_range=None, **kwargs):
        """Fold the low-stock list (+ threshold) into the home context.

        available_quantity is a Python property, so pull a small page and
        filter in-memory rather than denormalising a column for one tile.
        """
        from plugins.installed.inventory.models import StockLevel  # noqa: PLC0415
        from plugins.installed.inventory.services import low_stock_threshold  # noqa: PLC0415

        threshold = low_stock_threshold()
        candidates = list(
            StockLevel.objects.select_related('variant', 'variant__product', 'warehouse').filter(
                quantity__lte=threshold + 50
            )[:200]
        )
        value['low_stock'] = sorted(
            (sl for sl in candidates if sl.available_quantity <= threshold),
            key=lambda sl: sl.available_quantity,
        )[:6]
        value['low_stock_threshold'] = threshold
        return value

    def on_stock_summary(self, value=None, product_ids=None, **kwargs):
        """PRODUCT_STOCK_SUMMARY: add this app's stock answer for ``product_ids``."""
        from plugins.installed.inventory.services import stock_summary  # noqa: PLC0415

        answer = dict(value or {})
        answer.update(stock_summary(product_ids))
        return answer

    def on_variant_stock_summary(self, value=None, variant_ids=None, **kwargs):
        """VARIANT_STOCK_SUMMARY: the units the reservation could take, per variant."""
        from plugins.installed.inventory.services import variant_stock_summary  # noqa: PLC0415

        answer = dict(value or {})
        answer.update(variant_stock_summary(variant_ids))
        return answer

    def reserve_stock_filter(self, value=0, order=None, **kwargs):
        # Reserve stock when the order is created (before payment). Raises
        # InsufficientStockError on a short — the filter is fired with
        # raise_errors=True so that propagates and rolls back the order.
        from plugins.installed.inventory.services import InventoryService  # noqa: PLC0415

        if order is None:
            return value
        return InventoryService.reserve_for_order(order)

    def on_order_paid(self, order, **kwargs):
        # Convert reservations into permanent decrements once payment lands.
        from plugins.installed.inventory.services import InventoryService  # noqa: PLC0415

        InventoryService.commit_for_order(order)

    def on_order_cancelled(self, order, **kwargs):
        # Release reservations on cancel.
        from plugins.installed.inventory.services import InventoryService  # noqa: PLC0415

        InventoryService.release_reservation(order)

    def on_return_refunded(self, return_request=None, **kwargs):
        """Restock the variant rows for items in a refunded return —
        without this, returned merchandise becomes phantom stock."""
        if return_request is None:
            return
        from plugins.installed.inventory.services import InventoryService  # noqa: PLC0415

        try:
            InventoryService.restock_for_return(return_request)
        except Exception as e:  # noqa: BLE001 — never break the return flow
            import logging  # noqa: PLC0415

            logging.getLogger('morpheus.inventory').warning(
                'inventory: restock for rma=%s failed: %s',
                getattr(return_request, 'rma_number', '?'),
                e,
                exc_info=True,
            )

    def contribute_dashboard_cards(self) -> list:
        # A card on the Products landing, beside other apps' cards.
        return [
            DashboardCard(
                section='products',
                title='Stockout forecast',
                data='plugins.installed.inventory.cards.stockout_card',
                url='/dashboard/apps/inventory/stockout-forecast/',
                cta='Open forecast',
                icon='trending-down',
                order=80,
                capability='inventory.read',
            )
        ]

    def contribute_dashboard_pages(self) -> list:
        from morpheus.app import DashboardPage  # noqa: PLC0415

        return [
            DashboardPage(
                label='Warehouses',
                slug='warehouses',
                view='plugins.installed.inventory.dashboard.warehouses',
                icon='package',
                section='shipping',
                order=20,
                nav='settings',
                url='/dashboard/inventory/warehouses/',
                hint='Where stock is kept, and moving it between them',
            ),
            DashboardPage(
                label='Stockout forecast',
                slug='stockout-forecast',
                view='plugins.installed.inventory.views.stockout_forecast_view',
                icon='trending-down',
                section='products',
                nav='hidden',
                order=80,
            ),
        ]

    def contribute_agent_tools(self) -> list:
        from plugins.installed.inventory.agent_tools import (  # noqa: PLC0415
            adjust_stock_tool,
            create_warehouse_tool,
            list_back_in_stock_tool,
            low_stock_report_tool,
            schedule_price_change_tool,
            set_stock_tool,
            stock_levels_tool,
            stockout_forecast_tool,
            transfer_stock_tool,
            warehouses_tool,
        )

        return [
            low_stock_report_tool,
            stock_levels_tool,
            warehouses_tool,
            adjust_stock_tool,
            set_stock_tool,
            transfer_stock_tool,
            create_warehouse_tool,
            list_back_in_stock_tool,
            schedule_price_change_tool,
            stockout_forecast_tool,
        ]

    def contribute_skills(self) -> list:
        """The Inventory skill — opt in via skills=['inventory'] for stock
        queries, restocks, and scheduled price changes."""
        from core.agents import Skill  # noqa: PLC0415
        from plugins.installed.inventory.agent_tools import (  # noqa: PLC0415
            adjust_stock_tool,
            create_warehouse_tool,
            list_back_in_stock_tool,
            low_stock_report_tool,
            schedule_price_change_tool,
            set_stock_tool,
            stock_levels_tool,
            transfer_stock_tool,
            warehouses_tool,
        )

        return [
            Skill(
                name='inventory',
                label='Inventory Operations',
                description='Stock levels, restocks, transfers, scheduled price changes.',
                tools=(
                    low_stock_report_tool,
                    stock_levels_tool,
                    warehouses_tool,
                    adjust_stock_tool,
                    set_stock_tool,
                    transfer_stock_tool,
                    create_warehouse_tool,
                    list_back_in_stock_tool,
                    schedule_price_change_tool,
                ),
                system_prompt_prelude=(
                    'You are working on inventory. Standard workflow:\n'
                    '  • Read first with stock_levels or low_stock_report; never '
                    'assume stock state.\n'
                    '  • set_stock writes a counted number, adjust_stock a change '
                    '(a delivery, a write-off); confirm the SKU, warehouse and '
                    'quantity with the merchant before either. Each leaves a '
                    'movement in the audit log.\n'
                    '  • transfer_stock moves free units only; units held for open '
                    'orders stay put.\n'
                    '  • Scheduled price changes are reversible — surface the '
                    'effective date so the merchant can spot conflicts.'
                ),
            )
        ]
