"""The gift-cards card on the Marketing overview (DashboardCard)."""

from __future__ import annotations

from django.db.models import Count, Sum


def gift_cards_card(request) -> dict:
    """What active gift cards still owe shoppers — the store's liability —
    per currency."""
    from djmoney.money import Money

    from core.templatetags.morph import money_filter
    from plugins.installed.gift_cards.models import GiftCard

    by_currency = list(
        GiftCard.objects.filter(state='active')
        .values('balance_currency')
        .annotate(total=Sum('balance'), cards=Count('id'))
        .order_by('-total')
    )
    if not by_currency:
        return {'empty': 'No active gift cards.'}
    first = by_currency[0]
    cards = sum(row['cards'] for row in by_currency)
    rows = [
        (row['balance_currency'], money_filter(Money(row['total'] or 0, row['balance_currency'])))
        for row in by_currency[1:4]
    ]
    return {
        'value': money_filter(Money(first['total'] or 0, first['balance_currency'])),
        'caption': f'outstanding on {cards} active card{"s" if cards != 1 else ""}',
        'rows': rows,
    }
