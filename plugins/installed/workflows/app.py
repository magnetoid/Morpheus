"""workflows plugin manifest."""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin
from morpheus.core import events

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
        self.register_hook(events.DASHBOARD_SEARCH, self.on_dashboard_search)
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

    def on_dashboard_search(self, value, query='', words=None, **kwargs):
        """Workflows (by name or description) in the dashboard's search box."""
        from plugins import dashboard_search as ds
        from plugins.installed.workflows.models import Workflow

        return ds.add(
            value,
            Workflow,
            query,
            words,
            fields=('name', 'description'),
            section='Workflows',
            kind='workflow',
            icon='workflow',
            capability='system.write',
            label=lambda w: w.name,
            hint=lambda w: f'Workflow · {w.trigger}',
            url=lambda w: f'/dashboard/workflows/{w.pk}/',
        )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.workflows.agent_tools import workflows_run_tool  # noqa: PLC0415

        return [workflows_run_tool]

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
                hint='When something happens, do something',
            ),
        ]
