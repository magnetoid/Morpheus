"""Gift card services."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone
from djmoney.money import Money

logger = logging.getLogger('morpheus.gift_cards')


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


def sellable_skus() -> set[str]:
    """The configured set of order-item SKUs that mean "this is a gift-card
    purchase" (Settings → Gift cards). Upper-cased; empty set disables."""
    from plugins.registry import plugin_registry

    raw = str(plugin_registry.config_value('gift_cards', 'sellable_skus', 'GIFT-CARD') or '')
    return {s.strip().upper() for s in raw.split(',') if s.strip()}


def issue_for_order(order) -> list:
    """Issue purchased gift cards for a paid order — idempotent, 1 card/unit.

    An order item whose SKU is in ``sellable_skus()`` is a gift-card
    purchase: every unit becomes one card worth the unit price, delivered to
    the order email. Idempotency: cards for an order carry
    ``note='Purchased in order <number>'`` — a re-fired ORDER_PAID (webhook
    replay) issues only the missing remainder, in deterministic item order.
    """
    from core.utils.orders import order_email
    from plugins.installed.gift_cards.models import GiftCard

    skus = sellable_skus()
    if not skus:
        return []
    email = order_email(order)
    note = f'Purchased in order {order.order_number}'
    wanted = []  # one entry per unit, deterministic ordering
    for item in order.items.all().order_by('pk'):
        if (item.sku or '').strip().upper() in skus:
            wanted.extend([item.unit_price] * int(item.quantity or 0))
    if not wanted:
        return []
    from plugins.installed.orders.models import Order

    # Serialize per order: lock the order row so a concurrent ORDER_PAID (e.g. a
    # double-clicked manual "mark paid", which — unlike the Stripe/PayPal webhook
    # path — holds no lock) can't both read existing=0 and mint duplicate
    # real-money cards. On Postgres this blocks the second caller until the first
    # commits; it then sees existing=len(wanted) and issues nothing.
    issued = []
    with transaction.atomic():
        Order.objects.select_for_update().filter(pk=order.pk).first()
        existing = GiftCard.objects.filter(note=note).count()
        for amount in wanted[existing:]:
            issued.append(issue(amount=amount, email=email, note=note))
    # Deliver outside the lock (send is deferred to on_commit anyway).
    for card in issued:
        _send_delivery(card, order)
    if issued:
        logger.info('gift_cards: issued %s card(s) for order %s', len(issued), order.order_number)
    return issued


def _send_delivery(card, order) -> None:
    """Email the purchased card's code to the buyer (merchant-editable)."""
    from core.emails import send_templated_email
    from core.utils.orders import order_email
    from core.utils.site import site_base_url

    send_templated_email(
        'gift_card_delivery',
        to=order_email(order) or None,
        subject='Your gift card',
        ctx={
            'code': card.code,
            'amount': card.initial_value,
            'order_number': order.order_number,
            'store_url': site_base_url(),
        },
    )
