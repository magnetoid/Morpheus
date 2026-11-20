"""``/withdraw/``: "Withdraw from contract here" (EU CRD Art. 11a; v0.181.0).

Two steps, as the law asks. The form takes the customer's name, the order
number and the email the acknowledgement goes to; the second page repeats what
was typed and the "Confirm withdrawal" button submits it. Only then is the order
looked up (``orders.withdrawal.find_order``: number AND email), so a guest learns
nothing about an order from either page, and the last page reads the same
whether or not the details matched.

A customer reaches the form already identified from their account's order page
(their own order) or the order email's link (the order's public token); the
second page then lists what can be withdrawn and why not.
"""

from __future__ import annotations

import logging
import secrets

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import Http404
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from morpheus.app.views import redirect, render

logger = logging.getLogger('morpheus.returns_portal')

_DRAFT = 'withdrawal_draft'
_KNOWN = 'withdrawal_order'
_DONE = 'withdrawal_done'
#: Submissions an address may make per hour, at each step.
_PER_HOUR = 10
_SEO = {'seo_title': 'Withdraw from contract', 'seo_noindex_reason': 'a form about one order'}


def _require_on():
    from plugins.installed.returns_portal import withdrawal  # noqa: PLC0415

    if not withdrawal.enabled():
        raise Http404('Not found')


def _throttled(request, step: str) -> bool:
    from core.ratelimit import client_ip  # noqa: PLC0415
    from core.utils.rate_limit import RateLimitExceeded, check_and_consume  # noqa: PLC0415

    try:
        check_and_consume(
            key=f'withdrawal:{step}:{client_ip(request)}',
            max_per_window=_PER_HOUR,
            window_seconds=3600,
        )
    except RateLimitExceeded:
        return True
    return False


def _known_order(request):
    """The order this visitor is known to hold (their own, or reached by its token)."""
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    pk = request.session.get(_KNOWN)
    return Order.objects.filter(pk=pk).first() if pk else None


def _identify(request):
    """Remember the order a link names when the visitor may see it."""
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    number = (request.GET.get('order') or '').strip()
    if not number:
        return None
    order = Order.objects.filter(order_number__iexact=number).first()
    if order is None:
        return None
    token = (request.GET.get('token') or '').strip()
    owner = request.user.is_authenticated and order.customer_id == request.user.pk
    by_token = bool(token) and secrets.compare_digest(token, order.public_token or '')
    if not (owner or by_token):
        return None
    request.session[_KNOWN] = str(order.pk)
    return order


@never_cache
@require_http_methods(['GET', 'POST'])
def withdraw(request):
    """Step 1 (GET, and a POST that fails), then step 2 (a POST that passes)."""
    _require_on()
    if request.method == 'GET':
        known = _identify(request)
        draft = {
            'name': _account_name(request),
            'number': known.order_number if known else '',
            'email': known.email if known else '',
        }
        return _form(request, draft)

    from core import bot_check  # noqa: PLC0415

    draft = {
        'name': (request.POST.get('name') or '').strip()[:200],
        'number': (request.POST.get('order_number') or '').strip()[:20],
        'email': (request.POST.get('email') or '').strip()[:254],
    }
    if _throttled(request, 'form'):
        return _form(request, draft, error='Too many tries. Please wait an hour and try again.')
    if not bot_check.passes(request, 'withdrawal'):
        return _form(request, draft, error=str(bot_check.REFUSED))
    if not (draft['name'] and draft['number'] and draft['email']):
        return _form(request, draft, error='Fill in your name, the order number and your email.')
    try:
        validate_email(draft['email'])
    except ValidationError:
        return _form(request, draft, error='Enter a valid email address.')
    request.session[_DRAFT] = draft
    return render(request, 'returns_portal/withdraw_confirm.html', _confirm_context(request, draft))


@never_cache
@require_http_methods(['POST'])
def confirm(request):
    """Step 2: "Confirm withdrawal". Records it when the details name an order."""
    from plugins.installed.orders.withdrawal import (  # noqa: PLC0415
        WithdrawalRefused,
        find_order,
    )
    from plugins.installed.orders.withdrawal import withdraw as record  # noqa: PLC0415
    from plugins.installed.returns_portal import withdrawal  # noqa: PLC0415

    _require_on()
    draft = request.session.get(_DRAFT)
    if not isinstance(draft, dict):
        return redirect(reverse('returns_portal:withdraw'))
    if _throttled(request, 'confirm'):
        return _form(request, draft, error='Too many tries. Please wait an hour and try again.')
    known = _known_order(request)
    if known is not None and known.order_number.lower() == draft['number'].lower():
        order = known
    else:
        order = find_order(draft['number'], draft['email'])
    request.session.pop(_DRAFT, None)
    request.session.pop(_DONE, None)
    if order is None:
        logger.info('returns_portal: a withdrawal named no order')
        return redirect(reverse('returns_portal:withdraw_sent'))
    try:
        notice = record(
            order,
            name=draft['name'],
            email=draft['email'],
            days=withdrawal.days(),
            actor=request.user,
        )
    except WithdrawalRefused as e:
        return _form(request, draft, error=str(e))
    if order is known:
        request.session[_DONE] = str(notice.pk)
    return redirect(reverse('returns_portal:withdraw_sent'))


@never_cache
def sent(request):
    """The last page: the same words whether or not the details matched an order."""
    from plugins.installed.orders.models import WithdrawalNotice  # noqa: PLC0415

    _require_on()
    pk = request.session.get(_DONE)
    notice = WithdrawalNotice.objects.filter(pk=pk).select_related('order').first() if pk else None
    return render(request, 'returns_portal/withdraw_sent.html', {'notice': notice, **_SEO})


def _account_name(request) -> str:
    user = request.user
    if not user.is_authenticated:
        return ''
    return ' '.join(p for p in (user.first_name, user.last_name) if p).strip()


def _form(request, draft: dict, *, error: str = ''):
    return render(
        request,
        'returns_portal/withdraw.html',
        {'draft': draft, 'error': error, **_SEO},
    )


def _confirm_context(request, draft: dict) -> dict:
    """What step 2 shows: the details typed, and for an order the visitor holds,
    each line with whether it can be withdrawn."""
    from plugins.installed.orders.withdrawal import line_rights  # noqa: PLC0415
    from plugins.installed.returns_portal import withdrawal  # noqa: PLC0415

    known = _known_order(request)
    rights = []
    if known is not None and known.order_number.lower() == draft['number'].lower():
        rights = line_rights(known, days=withdrawal.days())
    return {'draft': draft, 'known_order': known if rights else None, 'rights': rights, **_SEO}
