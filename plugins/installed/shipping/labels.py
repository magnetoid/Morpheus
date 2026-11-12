"""Carrier labels for an order's parcels, bought from Shippo or EasyPost.

Two ways in, used by the order page's panel and Linda's ``shipping.buy_label``:

* ``label_for_parcel``: a label for a parcel already recorded. It fills the
  parcel's tracking when it has none, and the buyer is then sent it
  (``FULFILLMENT_TRACKING_ADDED``).
* ``ship_with_label``: one label for the units still open, then the parcel is
  recorded with the label's tracking (``orders.fulfilment.create_fulfillment``),
  so the usual shipping email carries it.

Buying a label spends the merchant's money, so a purchase runs in three steps:

1. Under a row lock, check the order and write a *purchasing* ``ShippingLabel``,
   then commit: a second click finds it and stops.
2. Ask the carrier, outside any transaction (two requests, up to
   ``TIMEOUT_S`` each, hold no lock). A refusal deletes the row; an answer that
   does not say whether the carrier charged marks it *unconfirmed*.
3. Store the carrier's answer and commit, and only then record the parcel or its
   tracking, each in its own transaction: nothing that fails afterwards can lose
   a label that was paid for.

Neither function may run inside a caller's transaction, or step 1 would not
commit. The carrier is sent a fresh shipment each time (a quoted rate expires),
and the cheapest rate it returns is bought.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('morpheus.shipping')

PROVIDERS = ('shippo', 'easypost')
NAMES = {'shippo': 'Shippo', 'easypost': 'EasyPost'}
MIN_WEIGHT_KG = Decimal('0.05')
TIMEOUT_S = 15
# A purchase still "being bought" after this long was cut off (a restart, a
# killed worker) before it could store the carrier's answer.
STALE_AFTER = timedelta(minutes=5)


class LabelError(ValueError):
    """A label that could not be bought; the message is fit for the merchant."""


class LabelUnconfirmed(LabelError):
    """The carrier was asked to buy a label and its answer does not say whether
    it did (no answer, an unreadable one, a label still queued)."""

    def __init__(self, message: str, provider_id: str = ''):
        super().__init__(message)
        self.provider_id = provider_id


def _config() -> dict:
    from plugins.installed.shipping.services import _shipping_config  # noqa: PLC0415

    return _shipping_config()


def _origin(cfg: dict, provider: str) -> dict:
    if provider == 'easypost':
        return cfg.get('easypost_default_address') or cfg.get('shippo_default_address') or {}
    return cfg.get('shippo_default_address') or {}


def _has_postcode(address: dict) -> bool:
    return bool(address.get('country') and (address.get('zip') or address.get('postal_code')))


def configured_providers(cfg: dict | None = None) -> list[str]:
    """The carrier services this store can buy a label from: key and origin set."""
    cfg = _config() if cfg is None else cfg
    return [
        p
        for p in PROVIDERS
        if (cfg.get(f'{p}_api_key') or '').strip()
        and isinstance(_origin(cfg, p), dict)
        and _has_postcode(_origin(cfg, p))
    ]


def _address(raw: dict, *, fallback_name: str, email: str = '') -> dict:
    """An address in the carriers' shape, from a stored order or origin address."""
    name = (
        raw.get('name') or ' '.join(filter(None, (raw.get('first_name'), raw.get('last_name'))))
    ).strip()
    return {
        'name': name or fallback_name,
        'street1': raw.get('street1') or raw.get('address_line1') or raw.get('line1') or '',
        'street2': raw.get('street2') or raw.get('address_line2') or raw.get('line2') or '',
        'city': raw.get('city') or '',
        'state': raw.get('state') or raw.get('region') or '',
        'zip': raw.get('zip') or raw.get('postal_code') or '',
        'country': (raw.get('country') or '').upper(),
        'phone': raw.get('phone') or '',
        'email': raw.get('email') or email,
    }


def _weight_kg(lines) -> Decimal:
    from plugins.installed.shipping.services import product_weight_kg  # noqa: PLC0415

    total = sum(
        (product_weight_kg(item.product) * qty for item, qty in lines if item.product),
        Decimal('0'),
    )
    return max(total, MIN_WEIGHT_KG)


def _post(provider: str, url: str, payload: dict, *, api_key: str, buying: bool = False) -> dict:
    """POST to the carrier. ``buying`` marks the request that charges: when it
    gets no readable answer, the charge may still have happened."""
    import requests  # noqa: PLC0415

    name = NAMES[provider]
    unsure = (
        f'{name} gave no clear answer while buying the label. Check your {name} account '
        'before buying again: the label may have been bought.'
    )
    if provider == 'shippo':
        auth = {'headers': {'Authorization': f'ShippoToken {api_key}'}}
    else:
        auth = {'auth': (api_key, '')}
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT_S, **auth)
    except requests.RequestException as exc:
        logger.warning('%s: label request failed: %s', provider, exc)
        if buying:
            raise LabelUnconfirmed(unsure) from None
        raise LabelError(f'{name} did not answer; try again in a minute.') from None
    if resp.status_code >= 400:
        logger.warning('%s: label request refused (%s): %s', provider, resp.status_code, resp.text)
        if buying and resp.status_code >= 500:
            # A gateway error can come back after the carrier has charged.
            raise LabelUnconfirmed(unsure)
        raise LabelError(
            f'{name} refused the label (HTTP {resp.status_code}). Check both addresses '
            "and the products' weights; the details are in the error log."
        )
    try:
        return resp.json()
    except ValueError:
        if buying:
            raise LabelUnconfirmed(unsure) from None
        raise LabelError(f'{name} sent an answer that could not be read.') from None


def _cheapest(rates: list, amount_key: str, name: str) -> dict:
    priced = []
    for rate in rates or []:
        try:
            priced.append((Decimal(str(rate.get(amount_key))), rate))
        except (InvalidOperation, TypeError):
            continue
    if not priced:
        raise LabelError(f'{name} offered no rate for this parcel and address.')
    return min(priced, key=lambda pair: pair[0])[1]


def _money(amount, currency) -> tuple[Decimal | None, str]:
    try:
        return Decimal(str(amount)).quantize(Decimal('0.01')), str(currency or '')[:3].upper()
    except (InvalidOperation, TypeError):
        return None, ''


def _shippo(api_key: str, origin: dict, dest: dict, weight_kg: Decimal) -> dict:
    parcel = {
        'length': '10',
        'width': '10',
        'height': '10',
        'distance_unit': 'cm',
        'weight': str(int(weight_kg * 1000)),
        'mass_unit': 'g',
    }
    shipment = _post(
        'shippo',
        'https://api.goshippo.com/shipments/',
        {'address_from': origin, 'address_to': dest, 'parcels': [parcel], 'async': False},
        api_key=api_key,
    )
    rate = _cheapest(shipment.get('rates'), 'amount', 'Shippo')
    txn = _post(
        'shippo',
        'https://api.goshippo.com/transactions/',
        {'rate': rate.get('object_id'), 'label_file_type': 'PDF', 'async': False},
        api_key=api_key,
        buying=True,
    )
    status = str(txn.get('status') or '')
    if status == 'ERROR':
        texts = [str(m.get('text') or '') for m in txn.get('messages') or [] if isinstance(m, dict)]
        logger.warning('shippo: label not created: %s', texts)
        reason = next((t for t in texts if t), 'no reason given')
        raise LabelError(f'Shippo could not create the label: {reason[:200]}')
    if status != 'SUCCESS' or not txn.get('label_url'):
        logger.warning('shippo: label transaction %s is %s', txn.get('object_id'), status)
        raise LabelUnconfirmed(
            f'Shippo has not finished the label (status {status[:20] or "unknown"}). Check your '
            'Shippo account before buying again.',
            provider_id=str(txn.get('object_id') or ''),
        )
    cost, currency = _money(rate.get('amount'), rate.get('currency'))
    return {
        'provider': 'shippo',
        'provider_id': str(txn.get('object_id') or '')[:120],
        'label_url': str(txn['label_url']),
        'tracking_number': str(txn.get('tracking_number') or '')[:200],
        'tracking_url': str(txn.get('tracking_url_provider') or ''),
        'carrier': str(rate.get('provider') or '')[:100],
        'service': str((rate.get('servicelevel') or {}).get('name') or '')[:120],
        'cost_amount': cost,
        'cost_currency': currency,
    }


def _easypost(api_key: str, origin: dict, dest: dict, weight_kg: Decimal) -> dict:
    shipment = _post(
        'easypost',
        'https://api.easypost.com/v2/shipments',
        {
            'shipment': {
                'from_address': origin,
                'to_address': dest,
                'parcel': {'weight': float(weight_kg * Decimal('35.274'))},
            }
        },
        api_key=api_key,
    )
    rate = _cheapest(shipment.get('rates'), 'rate', 'EasyPost')
    bought = _post(
        'easypost',
        f'https://api.easypost.com/v2/shipments/{shipment.get("id")}/buy',
        {'rate': {'id': rate.get('id')}},
        api_key=api_key,
        buying=True,
    )
    label_url = (bought.get('postage_label') or {}).get('label_url')
    if not label_url:
        raise LabelUnconfirmed(
            'EasyPost answered without a label. Check your EasyPost account before buying again.',
            provider_id=str(bought.get('id') or shipment.get('id') or ''),
        )
    cost, currency = _money(rate.get('rate'), rate.get('currency'))
    return {
        'provider': 'easypost',
        'provider_id': str(bought.get('id') or shipment.get('id') or '')[:120],
        'label_url': str(label_url),
        'tracking_number': str(bought.get('tracking_code') or '')[:200],
        'tracking_url': str((bought.get('tracker') or {}).get('public_url') or ''),
        'carrier': str(rate.get('carrier') or '')[:100],
        'service': str(rate.get('service') or '')[:120],
        'cost_amount': cost,
        'cost_currency': currency,
    }


def _plan(order, provider: str | None) -> dict:
    """Which carrier and addresses a label for ``order`` uses; no request is sent."""
    cfg = _config()
    available = configured_providers(cfg)
    if not available:
        raise LabelError('Set up Shippo or EasyPost on the Shipping page first.')
    provider = provider or available[0]
    if provider not in available:
        raise LabelError(f'{provider} is not set up on the Shipping page.')
    dest = _address(order.shipping_address or {}, fallback_name='Customer', email=order.email)
    if not (dest['country'] and dest['zip'] and dest['street1']):
        raise LabelError('The order has no full shipping address to put on a label.')
    return {
        'provider': provider,
        'api_key': cfg[f'{provider}_api_key'].strip(),
        'origin': _address(_origin(cfg, provider), fallback_name='Warehouse'),
        'dest': dest,
    }


def _buy(label, plan: dict, lines) -> dict:
    """Step 2 and 3: ask the carrier for the label the *purchasing* row
    ``label`` stands for, then store its answer and commit."""
    from plugins.installed.shipping.models import ShippingLabel  # noqa: PLC0415

    buy = _shippo if plan['provider'] == 'shippo' else _easypost
    rows = ShippingLabel.objects.filter(pk=label.pk)
    try:
        data = buy(plan['api_key'], plan['origin'], plan['dest'], _weight_kg(lines))
    except LabelUnconfirmed as exc:
        rows.update(status='unconfirmed', fulfillment=None, provider_id=exc.provider_id[:120])
        raise
    except LabelError:
        rows.delete()  # refused before anything was charged
        raise
    except Exception:
        # Not known whether the carrier charged: keep the row for the merchant to check.
        logger.exception('shipping: label purchase for order %s failed', label.order_id)
        rows.update(status='unconfirmed', fulfillment=None)
        raise LabelUnconfirmed(
            f'Something went wrong while buying the label. Check your {NAMES[plan["provider"]]} '
            'account before buying again; the details are in the error log.'
        ) from None
    try:
        with transaction.atomic():
            rows.update(status='bought', **data)
    except Exception:
        # Paid for, but its answer cannot be stored (a URL too long for its column).
        logger.exception('shipping: label for order %s could not be stored', label.order_id)
        rows.update(status='unconfirmed', fulfillment=None, provider_id=data['provider_id'])
        raise LabelUnconfirmed(
            f'{NAMES[plan["provider"]]} sold the label (reference {data["provider_id"]}), but '
            'it could not be stored here. Open it in your account; do not buy it again.'
        ) from None
    label.refresh_from_db()
    return data


def _stale(label) -> bool:
    return label.status == 'purchasing' and label.created_at < timezone.now() - STALE_AFTER


def _cut_off_message(label) -> str:
    name = NAMES.get(label.provider, label.provider)
    return (
        f'An earlier label purchase did not finish. Check your {name} account; if no label '
        'was bought there, buy again.'
    )


def parcel_on(order, raw_id):
    """The parcel of ``order`` whose id is ``raw_id``, or None (a malformed id too)."""
    import uuid  # noqa: PLC0415

    from plugins.installed.orders.models import Fulfillment  # noqa: PLC0415

    try:
        pk = uuid.UUID(str(raw_id))
    except ValueError:
        return None
    return Fulfillment.objects.filter(pk=pk, order=order).first()


def _fill_tracking(fulfillment, data: dict) -> bool:
    """Give a parcel without tracking the label's; True when it got some."""
    if fulfillment.tracking_number or not data['tracking_number']:
        return False
    fulfillment.tracking_number = data['tracking_number']
    url = data['tracking_url']
    # Fulfillment.tracking_url holds 200 characters; a cut URL is a broken link.
    fulfillment.tracking_url = url if len(url) <= 200 else ''
    fulfillment.carrier = fulfillment.carrier or data['carrier']
    fulfillment.save(update_fields=['tracking_number', 'tracking_url', 'carrier'])
    order = fulfillment.order
    if not order.tracking_number:
        order.tracking_number = data['tracking_number']
        order.save(update_fields=['tracking_number'])
    return True


def label_for_parcel(fulfillment, *, provider: str | None = None):
    """Buy a label for a recorded parcel and return the ``ShippingLabel``."""
    from morpheus.core import MorpheusEvents, hook_registry  # noqa: PLC0415
    from plugins.installed.orders.models import Fulfillment  # noqa: PLC0415
    from plugins.installed.shipping.models import ShippingLabel  # noqa: PLC0415

    plan = _plan(fulfillment.order, provider)
    cut_off = None
    with transaction.atomic():
        parcel = (
            Fulfillment.objects.select_for_update().select_related('order').get(pk=fulfillment.pk)
        )
        existing = ShippingLabel.objects.filter(fulfillment=parcel).first()
        if existing is not None and _stale(existing):
            existing.status, existing.fulfillment = 'unconfirmed', None
            existing.save(update_fields=['status', 'fulfillment'])
            cut_off = _cut_off_message(existing)
        elif existing is not None and existing.status == 'purchasing':
            raise LabelError(
                'A label for this parcel is being bought; reload the page in a minute.'
            )
        elif existing is not None:
            raise LabelError('This parcel already has a label.')
        else:
            if parcel.order.status in ('cancelled', 'refunded'):
                raise LabelError(
                    f'An order that is {parcel.order.get_status_display().lower()} needs no label.'
                )
            lines = [
                (fi.order_item, fi.quantity)
                for fi in parcel.items.select_related('order_item__product')
            ]
            if not lines:
                raise LabelError('This parcel holds nothing to ship.')
            label = ShippingLabel.objects.create(
                order=parcel.order, fulfillment=parcel, provider=plan['provider']
            )
    if cut_off:
        raise LabelError(cut_off)

    data = _buy(label, plan, lines)

    try:
        with transaction.atomic():
            parcel = (
                Fulfillment.objects.select_for_update().select_related('order').get(pk=parcel.pk)
            )
            if _fill_tracking(parcel, data):

                def _announce():
                    try:
                        hook_registry.fire(
                            MorpheusEvents.FULFILLMENT_TRACKING_ADDED,
                            order=parcel.order,
                            fulfillment=parcel,
                        )
                    except Exception:  # noqa: BLE001 — the label is bought either way
                        logger.warning('shipping: tracking hook failed', exc_info=True)

                transaction.on_commit(_announce)
    except Exception:  # noqa: BLE001 — the label is stored; its tracking can be typed in
        logger.exception('shipping: label %s bought, parcel tracking not saved', label.pk)
    return label


def ship_with_label(order, *, provider: str | None = None):
    """Buy one label for the units still open, record the parcel with its
    tracking, and return the ``ShippingLabel``.

    The order is checked before anything is bought: it must still be as the
    caller loaded it and able to ship. A label that was paid for is kept even
    when the parcel cannot then be recorded: it stays on the order, on no
    parcel, and the ``LabelError`` says so.
    """
    from plugins.installed.orders.fulfilment import (  # noqa: PLC0415
        FULFILLABLE_STATUSES,
        FulfilmentError,
        create_fulfillment,
        open_lines,
    )
    from plugins.installed.orders.models import Order  # noqa: PLC0415
    from plugins.installed.shipping.models import ShippingLabel  # noqa: PLC0415

    plan = _plan(order, provider)
    cut_off = None
    with transaction.atomic():
        current = (
            Order.objects.select_for_update()
            .filter(pk=order.pk)
            .values_list('status', flat=True)
            .first()
        )
        if current != order.status:
            raise LabelError('This order changed meanwhile; reload it and try again.')
        if order.status not in FULFILLABLE_STATUSES:
            raise LabelError(
                f'An order that is {order.get_status_display().lower()} cannot ship a parcel.'
            )
        pending = ShippingLabel.objects.filter(
            order=order, fulfillment__isnull=True, status='purchasing'
        ).first()
        if pending is not None and _stale(pending):
            pending.status = 'unconfirmed'
            pending.save(update_fields=['status'])
            cut_off = _cut_off_message(pending)
        elif pending is not None:
            raise LabelError('A label for this order is being bought; reload the page in a minute.')
        else:
            lines = open_lines(order)
            if not lines:
                raise LabelError('Nothing in this order is left to ship.')
            label = ShippingLabel.objects.create(order=order, provider=plan['provider'])
    if cut_off:
        raise LabelError(cut_off)

    data = _buy(label, plan, lines)

    url = data['tracking_url']
    failure = None
    try:
        with transaction.atomic():
            parcel = create_fulfillment(
                order,
                {str(item.pk): units for item, units in lines},
                tracking_number=data['tracking_number'],
                tracking_url=url if len(url) <= 200 else '',
                carrier=data['carrier'],
            )
            ShippingLabel.objects.filter(pk=label.pk).update(fulfillment=parcel)
    except FulfilmentError as exc:
        failure = str(exc)
    except Exception:
        logger.exception('shipping: label %s bought, parcel not recorded', label.pk)
        failure = 'something went wrong while saving it; the details are in the error log'
    else:
        label.fulfillment = parcel
    if failure is not None:
        raise LabelError(
            f'The label was bought (tracking {data["tracking_number"] or "none"}) and is kept on '
            f'the order, but the parcel was not recorded: {failure}'
        )
    return label
