"""Gift cards dashboard views — list / issue / detail."""
from __future__ import annotations

import logging
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from djmoney.money import Money

from plugins.installed.gift_cards.forms import IssueGiftCardForm

logger = logging.getLogger('morpheus.gift_cards.dashboard')


@staff_member_required
def gift_cards_list(request: HttpRequest) -> HttpResponse:
    from plugins.installed.gift_cards.models import GiftCard

    state = (request.GET.get('state') or '').strip()
    search = (request.GET.get('q') or '').strip()
    qs = GiftCard.objects.all().order_by('-created_at')
    if state:
        qs = qs.filter(state=state)
    if search:
        qs = qs.filter(code__icontains=search.upper())
    cards = list(qs[:200])
    return render(request, 'gift_cards/list.html', {
        'cards': cards,
        'state': state,
        'search': search,
        'active_nav': 'marketing',
    })


@staff_member_required
def gift_card_new(request: HttpRequest) -> HttpResponse:
    from plugins.installed.gift_cards.services import issue

    if request.method == 'POST':
        form = IssueGiftCardForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                card = issue(
                    amount=Money(Decimal(str(cd['amount'])), cd['currency']),
                    email=cd.get('issued_to_email') or '',
                    issued_by=request.user if request.user.is_authenticated else None,
                    note=cd.get('note') or '',
                    expires_at=cd.get('expires_at'),
                )
                messages.success(
                    request,
                    f'Issued {card.initial_value} gift card · code {card.code}.',
                )
                return redirect('gift_cards:detail', card_id=card.id)
            except Exception as e:  # noqa: BLE001
                logger.warning('gift_cards: issue failed: %s', e, exc_info=True)
                messages.error(request, f'Could not issue card: {e}')
    else:
        form = IssueGiftCardForm()
    return render(request, 'gift_cards/new.html', {
        'form': form,
        'active_nav': 'marketing',
    })


@staff_member_required
def gift_card_detail(request: HttpRequest, card_id) -> HttpResponse:
    from plugins.installed.gift_cards.models import GiftCard, GiftCardLedger

    card = get_object_or_404(GiftCard, pk=card_id)

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        if action == 'disable':
            card.state = 'disabled'
            card.save(update_fields=['state', 'updated_at'])
            messages.success(request, 'Gift card disabled.')
        elif action == 'reactivate':
            card.state = 'active'
            card.save(update_fields=['state', 'updated_at'])
            messages.success(request, 'Gift card reactivated.')
        return redirect('gift_cards:detail', card_id=card.id)

    ledger = list(GiftCardLedger.objects.filter(card=card).order_by('-created_at')[:200])
    return render(request, 'gift_cards/detail.html', {
        'card': card,
        'ledger': ledger,
        'active_nav': 'marketing',
    })
