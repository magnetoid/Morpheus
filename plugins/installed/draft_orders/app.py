"""Draft Orders plugin manifest."""

from __future__ import annotations

import logging

from morpheus.app import Plugin

logger = logging.getLogger('morpheus.draft_orders')


class DraftOrdersPlugin(Plugin):
    name = 'draft_orders'
    label = 'Draft Orders'
    version = '1.1.0'
    description = (
        'Staff-built draft orders / quotes that can be priced, shared with '
        'the customer, then converted to a real order on payment. '
        'Surfaces inside the Orders dashboard rather than as a separate '
        'sidebar entry — drafts live next to real orders.'
    )
    has_models = True
    requires = ['orders']

    def ready(self) -> None:
        # URLs (index/detail/convert) stay registered so the link from the
        # Orders dashboard works. They just no longer appear as a separate
        # sidebar entry — drafts surface as a "View drafts →" link inside
        # the existing Orders dashboard.
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

    # No contribute_dashboard_pages — drafts live inside the Orders page.
