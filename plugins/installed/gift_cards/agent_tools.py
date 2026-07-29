"""Gift card agent tools."""

from __future__ import annotations

from decimal import Decimal

from djmoney.money import Money

from morpheus.core import ToolError, ToolResult, tool


@tool(
    name='gift_cards.issue',
    description='Issue a new gift card for a specified amount.',
    scopes=['gift_cards.write'],
    schema={
        'type': 'object',
        'properties': {
            'amount': {'type': 'number'},
            'currency': {'type': 'string', 'default': 'USD'},
            'email': {'type': 'string', 'description': 'Recipient email (optional)'},
            'note': {'type': 'string'},
        },
        'required': ['amount'],
    },
    requires_approval=True,
)
def issue_gift_card_tool(
    *, amount: float, currency: str = 'USD', email: str = '', note: str = ''
) -> ToolResult:
    from plugins.installed.gift_cards.services import issue

    card = issue(
        amount=Money(Decimal(str(amount)), currency),
        email=email,
        note=note,
    )
    return ToolResult(
        output={
            'code': card.code,
            'balance': str(card.balance.amount),
            'currency': str(card.balance.currency),
        },
        display=f'Issued {card.balance} → code {card.code}',
    )


@tool(
    name='gift_cards.lookup',
    description='Look up a gift card by code.',
    scopes=['gift_cards.read'],
    schema={
        'type': 'object',
        'properties': {'code': {'type': 'string'}},
        'required': ['code'],
    },
)
def lookup_gift_card_tool(*, code: str) -> ToolResult:
    from plugins.installed.gift_cards.services import lookup

    card = lookup(code)
    if card is None:
        raise ToolError(f'No gift card with code {code}')
    return ToolResult(
        output={
            'code': card.code,
            'state': card.state,
            'initial': str(card.initial_value.amount),
            'balance': str(card.balance.amount),
            'currency': str(card.balance.currency),
            'issued_to': card.issued_to_email or '',
        }
    )
