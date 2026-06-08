"""Gift cards plugin manifest."""

# Handler uses lazy imports (load-order-safe; the established plugin pattern).
# ruff: noqa: PLC0415
from __future__ import annotations

from morpheus import DashboardPage, Plugin, events


class GiftCardsPlugin(Plugin):
    name = 'gift_cards'
    label = 'Gift Cards'
    version = '1.0.0'
    description = (
        'Issue, redeem, and audit gift cards. Append-only ledger; safe '
        'currency math. Storefront redemption hooks into checkout.'
    )
    has_models = True

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.gift_cards.urls',
            prefix='dashboard/gift-cards/',
            namespace='gift_cards',
        )
        # Contribute the customer's gift-card count + total into the account
        # summary. ACCOUNT_SUMMARY_FIELDS is a filter that only fires while this
        # plugin is enabled, so disabling gift_cards removes the tile — instead
        # of storefront hard-coding the query (ADR 0013, the disable test).
        self.register_hook(events.ACCOUNT_SUMMARY_FIELDS, self.on_account_summary, priority=40)

    def on_account_summary(self, value, user=None, **kwargs):
        """Fold this customer's active gift cards into the account summary.
        Mutate the dict + return it; fail-soft — never break the account page."""
        if user is None:
            return value
        try:
            from decimal import Decimal

            from djmoney.money import Money

            from plugins.installed.gift_cards.models import GiftCard

            cards = GiftCard.objects.filter(issued_to_customer=user, state='active')
            count = cards.count()
            if count:
                value['gift_card_count'] = count
                total = sum((Decimal(str(c.balance.amount)) for c in cards), Decimal('0'))
                value['gift_card_total'] = Money(total, str(cards.first().balance.currency))
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger('morpheus.gift_cards').warning(
                'account_summary gift-card fold failed: %s', exc, exc_info=True
            )
        return value

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Gift cards',
                slug='gift_cards',
                view='plugins.installed.gift_cards.views.gift_cards_list',
                icon='gift',
                section='marketing',
                order=50,
            ),
        ]

    def contribute_agent_tools(self) -> list:
        from plugins.installed.gift_cards.agent_tools import (
            issue_gift_card_tool,
            lookup_gift_card_tool,
        )

        return [issue_gift_card_tool, lookup_gift_card_tool]
