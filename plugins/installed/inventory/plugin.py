from morpheus import Plugin


class InventoryPlugin(Plugin):
    name = "inventory"
    label = "Inventory"
    version = "1.0.0"
    description = "Warehouses, stock levels, movements, low-stock alerts; atomic reservations."
    has_models = True
    requires = ["catalog"]

    def ready(self):
        self.register_graphql_extension('plugins.installed.inventory.graphql.queries')
        self.register_graphql_extension('plugins.installed.inventory.graphql.mutations')
        self.register_hook('order.placed',    self.on_order_placed,    priority=5)
        self.register_hook('order.paid',      self.on_order_paid,      priority=5)
        self.register_hook('order.cancelled', self.on_order_cancelled, priority=5)
        self.register_hook('return.refunded', self.on_return_refunded, priority=5)
        self.register_celery_tasks('plugins.installed.inventory.tasks')

        # Beat schedules: detect abandoned carts every 30 min; apply price
        # schedules every 5 min. Operators can override via Django settings.
        self.register_celery_beat('inventory:find_abandoned_carts', {
            'task': 'inventory.find_abandoned_carts',
            'schedule': 60 * 30,
        })
        self.register_celery_beat('inventory:apply_price_schedules', {
            'task': 'inventory.apply_price_schedules',
            'schedule': 60 * 5,
        })
        # Redis fast-path: drift reconciliation every 5 min. No-ops if
        # no `stock:*` keys exist in Redis (i.e. fast-path not in use).
        self.register_celery_beat('inventory:reconcile_redis_stock', {
            'task': 'inventory.reconcile_redis_stock',
            'schedule': 60 * 5,
        })

    def on_order_placed(self, order, **kwargs):
        # Reserve stock when the order is created (before payment).
        from plugins.installed.inventory.services import InventoryService
        InventoryService.reserve_for_order(order)

    def on_order_paid(self, order, **kwargs):
        # Convert reservations into permanent decrements once payment lands.
        from plugins.installed.inventory.services import InventoryService
        InventoryService.commit_for_order(order)

    def on_order_cancelled(self, order, **kwargs):
        # Release reservations on cancel.
        from plugins.installed.inventory.services import InventoryService
        InventoryService.release_reservation(order)

    def on_return_refunded(self, return_request=None, **kwargs):
        """Restock the variant rows for items in a refunded return —
        without this, returned merchandise becomes phantom stock."""
        if return_request is None:
            return
        from plugins.installed.inventory.services import InventoryService
        try:
            InventoryService.restock_for_return(return_request)
        except Exception as e:  # noqa: BLE001 — never break the return flow
            import logging
            logging.getLogger('morpheus.inventory').warning(
                'inventory: restock for rma=%s failed: %s',
                getattr(return_request, 'rma_number', '?'), e, exc_info=True,
            )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.inventory.agent_tools import (
            adjust_stock_tool, list_back_in_stock_tool,
            low_stock_report_tool, schedule_price_change_tool,
        )
        return [
            low_stock_report_tool, adjust_stock_tool,
            list_back_in_stock_tool, schedule_price_change_tool,
        ]
