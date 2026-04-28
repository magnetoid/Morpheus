"""B2B plugin manifest."""
from __future__ import annotations

from morpheus import Plugin


class B2bPlugin(Plugin):
    name = 'b2b'
    label = 'B2B'
    version = '1.0.0'
    description = (
        'B2B commerce: quotes, per-account price lists, net-N payment terms. '
        'Reuses crm.Account; adds Quote/QuoteLine + PriceList + '
        'NetTermsAgreement models.'
    )
    has_models = True
    requires = ['catalog', 'orders', 'crm']

    def contribute_agent_tools(self) -> list:
        from plugins.installed.b2b.agent_tools import (
            list_quotes_tool, set_net_terms_tool,
        )
        return [list_quotes_tool, set_net_terms_tool]
