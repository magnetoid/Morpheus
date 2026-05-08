"""notifications_center plugin manifest."""
from __future__ import annotations

import logging

from morpheus import DashboardPage, Plugin

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
