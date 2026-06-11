"""Gift card services."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from djmoney.money import Money


def issue(
    *, amount: Money, email: str = '', issued_by=None, note: str = '', expires_at=None
) -> GiftCard:  # noqa: F821
    from plugins.installed.gift_cards.models import GiftCard, GiftCardLedger

    with transaction.atomic():
        card = GiftCard.objects.create(
            initial_value=amount,
            balance=amount,
            state='active',
            issued_to_email=email[:254] or '',
            issued_by=issued_by,
            note=note[:240],
            expires_at=expires_at,
        )
        GiftCardLedger.objects.create(
            card=card,
            kind='issue',
            amount_change=amount,
            balance_after=amount,
            actor=issued_by,
        )
    return card


def redeem(*, code: str, amount: Money, reference: str = '', actor=None) -> GiftCard:  # noqa: F821
    """Subtract `amount` from the card's balance. Raises if insufficient."""
    from core.money import assert_same_currency, money, sub
    from plugins.installed.gift_cards.models import GiftCard, GiftCardLedger

    with transaction.atomic():
        card = GiftCard.objects.select_for_update().get(code=code)
        if card.state != 'active':
            raise ValueError(f'Gift card {code} is not active.')
        if card.expires_at and card.expires_at < timezone.now():
            card.state = 'expired'
            card.save(update_fields=['state'])
            raise ValueError(f'Gift card {code} has expired.')
        assert_same_currency(card.balance, amount)
        if card.balance.amount < amount.amount:
            raise ValueError(f'Insufficient balance: {card.balance} < {amount}')
        new_balance = sub(card.balance, amount)
        card.balance = new_balance
        card.save(update_fields=['balance', 'updated_at'])
        GiftCardLedger.objects.create(
            card=card,
            kind='redeem',
            amount_change=money(-amount.amount, str(amount.currency)),
            balance_after=new_balance,
            reference=reference[:100],
            actor=actor,
        )
    return card


def lookup(code: str) -> GiftCard | None:  # noqa: F821
    from plugins.installed.gift_cards.models import GiftCard

    return GiftCard.objects.filter(code=code).first()
