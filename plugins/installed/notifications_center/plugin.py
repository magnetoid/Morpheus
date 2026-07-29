"""notifications_center plugin manifest."""

from __future__ import annotations

import logging

from morpheus.plugin import DashboardPage, Plugin

logger = logging.getLogger('morpheus.notifications_center')


class NotificationsCenterPlugin(Plugin):
    name = 'notifications_center'
    label = 'Notifications center'
    version = '0.1.0'
    description = (
        'Persistent staff inbox for events that need follow-up — pending '
        'RMAs, low-stock crossings, agent-run failures, overdue tasks. '
        'Bell badge in the topbar, full list page in the dashboard.'
    )
    has_models = True

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.notifications_center.urls',
            prefix='dashboard/notifications/',
            namespace='notifications_center',
        )
        # Subscribe to platform events that staff care about. RMA-created
        # already wires direct in orders.refunds; the rest funnel through
        # generic hook listeners here so the notifications plugin owns
        # all the fan-out shaping in one place.
        try:
            from morpheus.core import events

            self.register_hook(events.PRODUCT_LOW_STOCK, self._on_low_stock, priority=80)
            self.register_hook(events.PRODUCT_OUT_OF_STOCK, self._on_out_of_stock, priority=80)
        except Exception as e:  # noqa: BLE001
            logger.debug('notifications_center: inventory events unavailable: %s', e)
        try:
            from core.agents.events import AgentEvents

            self.register_hook(AgentEvents.RUN_FAILED, self._on_agent_failed, priority=80)
        except Exception as e:  # noqa: BLE001
            logger.debug('notifications_center: agent events unavailable: %s', e)

    @staticmethod
    def _on_low_stock(stock_level=None, **kwargs):
        if stock_level is None:
            return
        try:
            from plugins.installed.notifications_center.services import notify_all_staff

            variant = getattr(stock_level, 'variant', None)
            product = getattr(variant, 'product', None) if variant else None
            name = getattr(product, 'name', '') or getattr(variant, 'sku', '') or 'item'
            avail = getattr(stock_level, 'available_quantity', getattr(stock_level, 'quantity', 0))
            notify_all_staff(
                kind='inventory.low_stock',
                title=f'Low stock — {name}',
                body=f'Available: {avail}. Re-order soon to avoid going out of stock.',
                action_url='/dashboard/products/?status=active',
                icon='alert-triangle',
            )
        except Exception:  # noqa: BLE001, S110
            pass

    @staticmethod
    def _on_out_of_stock(stock_level=None, **kwargs):
        if stock_level is None:
            return
        try:
            from plugins.installed.notifications_center.services import notify_all_staff

            variant = getattr(stock_level, 'variant', None)
            product = getattr(variant, 'product', None) if variant else None
            name = getattr(product, 'name', '') or getattr(variant, 'sku', '') or 'item'
            notify_all_staff(
                kind='inventory.out_of_stock',
                title=f'Out of stock — {name}',
                body='This variant is now unavailable to shoppers. Re-stock or hide it.',
                action_url='/dashboard/products/?status=active',
                icon='x-octagon',
            )
        except Exception:  # noqa: BLE001, S110
            pass

    @staticmethod
    def _on_agent_failed(agent=None, run_id=None, error=None, **kwargs):
        try:
            from plugins.installed.notifications_center.services import notify_all_staff

            notify_all_staff(
                kind='agents.run_failed',
                title=f'Agent run failed — {agent or "unknown"}',
                body=str(error or '')[:500],
                action_url=f'/dashboard/agents/{run_id}/' if run_id else '/dashboard/agents/',
                icon='alert-octagon',
            )
        except Exception:  # noqa: BLE001, S110
            pass

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                slug='all',
                label='Notifications',
                section='developer',
                icon='bell',
                view='plugins.installed.notifications_center.views.notifications_list',
                order=40,
                nav='settings',
            ),
        ]
