from celery.schedules import crontab

from morpheus import Plugin, events


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
        self.register_graphql_extension('plugins.installed.inventory.graphql.queries')
        self.register_graphql_extension('plugins.installed.inventory.graphql.mutations')
        # Fail-closed stock gate: reserve inside create_from_cart's transaction
        # via a raise_errors filter so a short-stock order actually rolls back
        # (the plain order.placed bus swallows the InsufficientStockError → the
        # old subscription could never block an oversell).
        self.register_hook(events.ORDER_RESERVE_STOCK, self.reserve_stock_filter, priority=5)
        # Dashboard-home low-stock tile.
        self.register_hook(events.DASHBOARD_HOME_PANELS, self.on_dashboard_panels, priority=50)
        self.register_hook('order.paid', self.on_order_paid, priority=5)
        self.register_hook('order.cancelled', self.on_order_cancelled, priority=5)
        self.register_hook('return.refunded', self.on_return_refunded, priority=5)
        self.register_celery_tasks('plugins.installed.inventory.tasks')

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

    def on_dashboard_panels(self, value, date_range=None, **kwargs):
        """Fold the low-stock list (+ threshold) into the home context.

        available_quantity is a Python property, so pull a small page and
        filter in-memory rather than denormalising a column for one tile.
        """
        from plugins.installed.inventory.models import StockLevel  # noqa: PLC0415
        from plugins.registry import plugin_registry  # noqa: PLC0415

        ae_plugin = plugin_registry.get('advanced_ecommerce')
        threshold = int(ae_plugin.get_config_value('low_stock_threshold', 5)) if ae_plugin else 5
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

    def contribute_dashboard_pages(self) -> list:
        from morpheus import DashboardPage  # noqa: PLC0415

        return [
            DashboardPage(
                label='Stockout Forecast',
                slug='stockout-forecast',
                view='plugins.installed.inventory.views.stockout_forecast_view',
                icon='trending-down',
                section='catalog',
                nav='main',
            )
        ]

    def contribute_agent_tools(self) -> list:
        from plugins.installed.inventory.agent_tools import (  # noqa: PLC0415
            adjust_stock_tool,
            list_back_in_stock_tool,
            low_stock_report_tool,
            schedule_price_change_tool,
            stockout_forecast_tool,
        )

        return [
            low_stock_report_tool,
            adjust_stock_tool,
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
            list_back_in_stock_tool,
            low_stock_report_tool,
            schedule_price_change_tool,
        )

        return [
            Skill(
                name='inventory',
                label='Inventory Operations',
                description='Stock levels, restocks, scheduled price changes.',
                tools=(
                    low_stock_report_tool,
                    adjust_stock_tool,
                    list_back_in_stock_tool,
                    schedule_price_change_tool,
                ),
                system_prompt_prelude=(
                    'You are working on inventory. Standard workflow:\n'
                    '  • Read first with low_stock_report to see what needs '
                    'attention; never assume stock state.\n'
                    '  • Be extremely careful with adjust_stock — always confirm '
                    'the SKU and quantity with the merchant before applying. A '
                    'wrong adjust_stock corrupts the audit trail.\n'
                    '  • Scheduled price changes are reversible — surface the '
                    'effective date so the merchant can spot conflicts.'
                ),
            )
        ]
