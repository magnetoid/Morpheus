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


def reverse_redemption_for_order(order) -> list:
    """Re-credit any gift-card balance spent on ``order`` — idempotent.

    Fired from the gift_cards ``ORDER_CANCELLED`` subscriber so a shopper isn't
    out the card balance for an order that never shipped. A no-op when nothing
    was redeemed or the reversal already happened. Mirrors
    ``loyalty_points.reverse_redemption_for_order``.

    Scope: full reversal keyed on ``reference == order.order_number`` — correct
    for a cancel (the whole order is voided). A *partial* RMA refund would need
    to prorate the card credit; that path is deferred with the refund-discount
    correctness work (docs/plans/deep-debug-2026-07.md #4), so this only
    subscribes to ORDER_CANCELLED, exactly like loyalty.
    """
    from core.money import add, money
    from plugins.installed.gift_cards.models import GiftCard, GiftCardLedger

    reference = str(getattr(order, 'order_number', '') or getattr(order, 'pk', ''))
    if not reference:
        return []
    reversed_cards = []
    with transaction.atomic():
        redeems = list(GiftCardLedger.objects.filter(kind='redeem', reference=reference))
        for row in redeems:
            # Lock the card, THEN check idempotency, so two concurrent reversals
            # of the same order can't both write a refund row.
            card = GiftCard.objects.select_for_update().get(pk=row.card_id)
            if GiftCardLedger.objects.filter(
                kind='refund', reference=reference, card=card
            ).exists():
                continue
            # redeem wrote amount_change negative; credit back its magnitude.
            credit = money(-row.amount_change.amount, str(row.amount_change.currency))
            new_balance = add(card.balance, credit)
            card.balance = new_balance
            card.save(update_fields=['balance', 'updated_at'])
            GiftCardLedger.objects.create(
                card=card,
                kind='refund',
                amount_change=credit,
                balance_after=new_balance,
                reference=reference[:100],
            )
            reversed_cards.append(card)
    if reversed_cards:
        logger.info(
            'gift_cards: reversed %s redemption(s) for order %s',
            len(reversed_cards),
            reference,
        )
    return reversed_cards


def refund_redemption_for_order(order, refund) -> list:
    """Re-credit the gift-card tender in proportion to a refund — idempotent.

    A gift card spent at checkout is folded into ``Order.discount_total``, so
    ``RefundService._compute_refund`` nets it back OUT of the cash refund: the
    shopper is repaid only the cash they actually paid. Without this handler the
    card portion was simply kept by the merchant — the shopper lost that value
    on every refund and return (only a full ORDER_CANCELLED restored it).

    Proration: cash refund and card credit are both shares of the same returned
    goods, so ``refund.amount / order.total`` is the right fraction for each
    (a half-value return repays half the cash and half the card).

    Idempotency is per refund — the ledger row is keyed ``<order>:r:<refund pk>``
    — and the cumulative credit per card is capped at what was redeemed, so
    repeated events, retried webhooks, and several partial refunds can never
    return more than the shopper spent.
    """
    from decimal import Decimal

    from django.db.models import Q

    from core.money import add, money
    from plugins.installed.gift_cards.models import GiftCard, GiftCardLedger

    reference = str(getattr(order, 'order_number', '') or getattr(order, 'pk', ''))
    if not reference or refund is None:
        return []
    refund_ref = f'{reference}:r:{getattr(refund, "pk", "")}'[:100]

    total = Decimal(getattr(order.total, 'amount', 0) or 0)
    refunded = Decimal(getattr(getattr(refund, 'amount', None), 'amount', 0) or 0)
    if total <= 0:
        # Wholly tender-paid order: there is no cash denominator to prorate
        # against. Surface it rather than guessing an amount either way.
        logger.warning(
            'gift_cards: order %s has zero cash total — refund %s needs a manual '
            'card re-credit (cannot prorate)',
            reference,
            refund_ref,
        )
        return []
    fraction = min(Decimal('1'), max(Decimal('0'), refunded / total))
    if fraction <= 0:
        return []

    credited = []
    with transaction.atomic():
        for row in GiftCardLedger.objects.filter(kind='redeem', reference=reference):
            card = GiftCard.objects.select_for_update().get(pk=row.card_id)
            if GiftCardLedger.objects.filter(
                kind='refund', reference=refund_ref, card=card
            ).exists():
                continue  # this refund already credited this card
            currency = str(row.amount_change.currency)
            redeemed = -Decimal(row.amount_change.amount)  # redeem rows are negative
            already = sum(
                (
                    Decimal(r.amount_change.amount)
                    for r in GiftCardLedger.objects.filter(kind='refund', card=card).filter(
                        Q(reference=reference) | Q(reference__startswith=f'{reference}:r:')
                    )
                ),
                Decimal('0'),
            )
            credit_amount = min((redeemed * fraction).quantize(Decimal('0.01')), redeemed - already)
            if credit_amount <= 0:
                continue
            credit = money(credit_amount, currency)
            new_balance = add(card.balance, credit)
            card.balance = new_balance
            card.save(update_fields=['balance', 'updated_at'])
            GiftCardLedger.objects.create(
                card=card,
                kind='refund',
                amount_change=credit,
                balance_after=new_balance,
                reference=refund_ref,
            )
            credited.append(card)
    if credited:
        logger.info(
            'gift_cards: re-credited %s card(s) for refund %s (%.2f of order)',
            len(credited),
            refund_ref,
            float(fraction),
        )
    return credited


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
    from morpheus.core import site_base_url

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
