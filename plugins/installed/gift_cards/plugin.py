"""Gift cards plugin manifest."""
from __future__ import annotations

from morpheus import Plugin


class GiftCardsPlugin(Plugin):
    name = 'gift_cards'
    label = 'Gift Cards'
    version = '1.0.0'
    description = (
        'Issue, redeem, and audit gift cards. Append-only ledger; safe '
        'currency math. Storefront redemption hooks into checkout.'
    )
    has_models = True

    def contribute_agent_tools(self) -> list:
        from plugins.installed.gift_cards.agent_tools import (
            issue_gift_card_tool, lookup_gift_card_tool,
        )
        return [issue_gift_card_tool, lookup_gift_card_tool]
