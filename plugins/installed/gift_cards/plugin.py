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
        # Sellable gift cards: when a paid order contains an item whose SKU is
        # in the configured set, issue one card per unit + email the code.
        self.register_hook(events.ORDER_PAID, self.on_order_paid, priority=60)
        # Re-credit a spent gift card when its order is cancelled — otherwise a
        # cancel refunds only the cash charge and the card balance is lost
        # forever (mirrors loyalty's redemption reversal).
        self.register_hook(events.ORDER_CANCELLED, self.on_order_cancelled, priority=60)

    def on_order_paid(self, order=None, **kwargs):
        """Issue purchased gift cards on payment (idempotent; fail-soft —
        a card problem must never break webhook processing)."""
        if order is None:
            return
        try:
            from plugins.installed.gift_cards.services import issue_for_order

            issue_for_order(order)
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger('morpheus.gift_cards').warning(
                'gift-card issuance for order %s failed: %s',
                getattr(order, 'order_number', '?'),
                exc,
                exc_info=True,
            )

    def on_order_cancelled(self, order=None, **kwargs):
        """Re-credit any gift card spent on a cancelled order (idempotent,
        fail-soft — a reversal problem must never block the cancel)."""
        if order is None:
            return
        try:
            from plugins.installed.gift_cards.services import reverse_redemption_for_order

            reverse_redemption_for_order(order)
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger('morpheus.gift_cards').warning(
                'gift-card reversal for order %s failed: %s',
                getattr(order, 'order_number', '?'),
                exc,
                exc_info=True,
            )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'sellable_skus': {
                    'type': 'string',
                    'title': 'Gift-card product SKUs',
                    'description': (
                        'Comma-separated SKUs that mean "this order item is a '
                        'gift-card purchase" — each paid unit is issued as a '
                        'card worth its price and emailed to the buyer. '
                        'Create a virtual product with one of these SKUs to '
                        'sell gift cards on the storefront.'
                    ),
                    'default': 'GIFT-CARD',
                },
            },
        }

    def contribute_settings_panel(self):
        from morpheus import SettingsPanel

        return SettingsPanel(
            label='Gift cards',
            description='Sell gift cards on the storefront: which SKUs auto-issue a card.',
            schema=self.get_config_schema(),
            category='marketing',
        )

    def contribute_email_templates(self) -> list:
        from morpheus import EmailTemplateDef

        return [
            EmailTemplateDef(
                key='gift_card_delivery',
                label='Gift card — delivery',
                default_subject='Your gift card',
                group='Gift cards',
                description='Sent to the buyer with the card code once their order is paid.',
            ),
        ]

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
                # Canonical URL — the routes live under register_urls'
                # dashboard/gift-cards/ prefix; without this override the
                # sidebar linked the doubled /dashboard/apps/gift_cards/gift_cards/.
                url='/dashboard/gift-cards/',
            ),
        ]

    def contribute_agent_tools(self) -> list:
        from plugins.installed.gift_cards.agent_tools import (
            issue_gift_card_tool,
            lookup_gift_card_tool,
        )

        return [issue_gift_card_tool, lookup_gift_card_tool]
