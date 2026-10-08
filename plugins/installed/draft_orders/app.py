"""Draft Orders plugin manifest."""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin

logger = logging.getLogger('morpheus.draft_orders')


class DraftOrdersPlugin(Plugin):
    name = 'draft_orders'
    label = 'Draft Orders'
    version = '1.1.0'
    description = (
        'Staff-built draft orders / quotes that can be priced, shared with '
        'the customer, then converted to a real order on payment. '
        'A Drafts tab in the Orders section — drafts live next to real orders.'
    )
    has_models = True
    requires = ['orders']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.draft_orders.urls',
            prefix='dashboard/draft-orders/',
            namespace='draft_orders',
        )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.draft_orders.agent_tools import (
            convert_draft_tool,
            list_drafts_tool,
        )

        return [list_drafts_tool, convert_draft_tool]

    def contribute_dashboard_pages(self) -> list:
        # The Drafts tab of the Orders section. The shell used to hardcode
        # this link behind a template guard; contributed, it leaves with the
        # app on a disable.
        return [
            DashboardPage(
                label='Drafts',
                slug='drafts',
                view='plugins.installed.draft_orders.views.index',
                icon='file-pen',
                section='orders',
                order=20,
                url='/dashboard/draft-orders/',
            )
        ]
