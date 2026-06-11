"""workflows plugin manifest."""

from __future__ import annotations

import logging

from morpheus import DashboardPage, Plugin

logger = logging.getLogger('morpheus.workflows')


class WorkflowsPlugin(Plugin):
    name = 'workflows'
    label = 'Workflows'
    version = '0.1.0'
    description = (
        'Visual no-code automation. Pick a trigger event, set a condition, '
        'fire one or more actions — including "invoke an agent skill" '
        "for AI-powered workflows Shopify Flow can't do."
    )
    has_models = True

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.workflows.urls',
            prefix='dashboard/workflows/',
            namespace='workflows',
        )
        # Subscribe to every supported trigger event so the engine fires.
        try:
            from plugins.installed.workflows.engine import register_hook_listeners

            register_hook_listeners(self)
        except Exception as e:  # noqa: BLE001
            logger.warning('workflows: hook listener registration failed: %s', e)

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                slug='index',
                label='Workflows',
                section='developer',
                icon='git-branch',
                view='plugins.installed.workflows.views.index',
                order=20,
                nav='settings',
                url='/dashboard/workflows/',
            ),
        ]
