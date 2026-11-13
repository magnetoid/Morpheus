"""Helpers for resolving the active Market and applying price overrides."""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import validate_slug
from django.db import transaction

logger = logging.getLogger('morpheus.markets')


def _country_from_request(request) -> str:
    """Pick the visitor's country code.

    Priority: explicit `?country=XX` (debugging) → Cloudflare's
    `CF-IPCountry` header → empty string (caller treats as 'unknown').
    Always uppercased.
    """
    if request is None:
        return ''
    explicit = (request.GET.get('country') or '').strip().upper()
    if explicit:
        return explicit
    cf = (request.META.get('HTTP_CF_IPCOUNTRY') or '').strip().upper()
    if cf and cf not in ('XX', 'T1'):  # T1 = Tor, XX = unknown
        return cf
    return ''


def resolve_market(request) -> Market | None:  # noqa: F821
    """Pick the active market for the request. ``None`` if markets
    isn't configured yet."""
    try:
        from plugins.installed.markets.models import Market
    except Exception:  # noqa: BLE001
        return None

    explicit = (request.GET.get('market') or '').strip().lower() if request else ''
    if explicit:
        m = Market.objects.filter(code=explicit, is_active=True).first()
        if m is not None:
            return m

    country = _country_from_request(request)
    if country:
        # No DB-side JSON containment so we filter in Python — list of
        # active markets is small (single-digit / low-tens).
        for m in Market.objects.filter(is_active=True):
            if country in m.country_set:
                return m

    return Market.objects.filter(is_active=True, is_default=True).first()


def market_context(request) -> dict:
    """Used as a Django context processor — adds `active_market` and a
    light-weight `market_currency` to every storefront template.

    Wrapped in a broad except so that a missing table or any other
    transient DB issue can't take the entire storefront down via a
    failing context processor. Returns blank values on error.
    """
    try:
        m = resolve_market(request)
    except Exception as e:  # noqa: BLE001
        logger.debug('market_context: resolve_market failed: %s', e)
        m = None
    return {
        'active_market': m,
        'market_currency': m.currency if m is not None else '',
        'market_locale': m.default_locale if m is not None else '',
    }


# ── Channel-scoping helpers ───────────────────────────────────────────────────
#
# Saleor's "Channel" concept maps to the Market model here. The middleware
# already stashes `request.market` on every request; these helpers are what
# plugins call to FILTER their queries by the active channel. Today the
# scoping is opt-in (no FK on Product yet — that's a planned migration); the
# helpers degrade to "all rows" so call sites are forward-compatible with
# the future schema change.


def current_channel(request) -> Market | None:  # noqa: F821
    """Return the channel (Market) resolved for this request, or None.

    Equivalent to `request.market` but safe to call when the middleware
    didn't run (CLI, tests, async tasks)."""
    return getattr(request, 'market', None)


def channel_scope(queryset, request=None, *, channel=None):
    """Apply per-channel filtering to a queryset, when meaningful.

    Today this is a no-op for models without a `channels` M2M / `channel`
    FK (which is most models). Once Tier-1 #1 lands the actual schema
    migration, this function flips to:

        if hasattr(queryset.model, 'channels'):
            queryset = queryset.filter(channels=ch)
        elif hasattr(queryset.model, 'channel'):
            queryset = queryset.filter(channel=ch)

    Calling it now is forward-compatible — plugin authors get a single
    canonical chokepoint to thread through, and the day the schema
    arrives every call site picks up the behaviour for free.
    """
    ch = channel or (current_channel(request) if request else None)
    if ch is None:
        return queryset
    model = getattr(queryset, 'model', None)
    if model is None:
        return queryset
    # Forward-compatibility shim — once the FK / M2M ships these branches
    # actually filter. Today they fall through to the unmodified queryset
    # because the schema isn't there yet.
    if hasattr(model, '_meta'):
        names = {f.name for f in model._meta.get_fields()}
        if 'channels' in names:
            return queryset.filter(channels=ch).distinct()
        if 'channel' in names:
            return queryset.filter(channel=ch)
    return queryset


def channel_pk(request) -> str:
    """Convenience: the active channel's PK as a string, or '' if none."""
    ch = current_channel(request)
    return str(ch.pk) if ch is not None else ''


# ── The one write path for a market (dashboard form and Linda) ───────────────

ROUNDINGS = ('exact', 'whole', 'ninety_nine')
# Territories Babel lists that are not countries (Kosovo, XK, is one in practice).
_NOT_COUNTRIES = frozenset({'ZZ', 'EU', 'EZ', 'UN', 'QO', 'XA', 'XB'})


def _countries(raw) -> list[str]:
    from babel import Locale

    if isinstance(raw, str):
        raw = raw.replace('\n', ',').split(',')
    known = Locale('en').territories
    out: list[str] = []
    for item in raw or []:
        code = str(item).strip().upper()
        if not code:
            continue
        if len(code) != 2 or not code.isalpha() or code in _NOT_COUNTRIES or code not in known:
            raise ValidationError(f'"{item}" is not a country code (use two letters, like US).')
        if code not in out:
            out.append(code)
    return out


def save_market(data: dict, market=None):  # noqa: PLR0912, PLR0915
    """Create a market, or update ``market``, from plain values.

    When an existing market changes currency, its fixed product prices (typed in
    the old one) are removed; the count is on ``market.removed_fixed_prices``
    (``removed_prices_note`` words it).

    A key missing from ``data`` keeps the market's current value (a new market
    takes the model's defaults). Raises ``ValidationError`` with a sentence a
    merchant can read. A market is switched on only when prices can be quoted in
    its currency: the store's own, or one with an exchange rate.
    """
    from babel.numbers import list_currencies

    from core.pricing import exchange_rate, store_currency
    from plugins.installed.markets.models import Market
    from plugins.installed.markets.rates import parse_decimal

    def pick(key, default):
        if key in data:
            return data[key]
        return getattr(market, key) if market is not None else default

    code = str(pick('code', '') or '').strip().lower()
    try:
        validate_slug(code)
    except ValidationError:
        raise ValidationError(
            'The code is needed, in letters, numbers and dashes (like "eu").'
        ) from None
    if len(code) > 40:
        raise ValidationError('The code can be 40 characters at most.')
    if Market.objects.filter(code=code).exclude(pk=getattr(market, 'pk', None)).exists():
        raise ValidationError(f'There is already a market with the code "{code}".')

    label = str(pick('label', '') or '').strip()
    if not label:
        raise ValidationError('The market needs a name.')
    if len(label) > 120:
        raise ValidationError('The name can be 120 characters at most.')

    currency = str(pick('currency', 'USD') or '').strip().upper()
    if currency not in list_currencies():
        raise ValidationError(f'"{currency}" is not a currency code (use three letters, like EUR).')

    countries = _countries(pick('country_codes', []))

    locale = str(pick('default_locale', 'en') or 'en').strip()
    if len(locale) > 10:
        raise ValidationError('The language code can be 10 characters at most.')

    try:
        adjustment = parse_decimal(pick('base_price_adjustment_pct', 0) or 0)
    except (InvalidOperation, ValueError):
        raise ValidationError('The price adjustment must be a number.') from None
    if not adjustment.is_finite() or not Decimal(-90) <= adjustment <= Decimal(500):
        raise ValidationError('The price adjustment must be between -90 and 500 percent.')
    adjustment = adjustment.quantize(Decimal('0.01'))

    rounding = str(pick('rounding', 'exact') or 'exact')
    if rounding not in ROUNDINGS:
        raise ValidationError('Rounding must be exact, whole or ninety_nine.')

    is_active = bool(pick('is_active', True))
    is_default = bool(pick('is_default', False))

    if (
        is_active
        and currency != store_currency()
        and exchange_rate(store_currency(), currency) is None
    ):
        raise ValidationError(f'Add an exchange rate for {currency} first.')

    values = {
        'code': code,
        'label': label,
        'currency': currency,
        'country_codes': countries,
        'default_locale': locale,
        'base_price_adjustment_pct': adjustment,
        'rounding': rounding,
        'is_active': is_active,
        'is_default': is_default,
    }
    removed, old_currency = 0, ''
    with transaction.atomic():
        if market is None:
            market = Market.objects.create(**values)
        else:
            old_currency = (market.currency or '').upper()
            if old_currency != currency:
                # A fixed price was typed in the old currency; it means nothing in the new.
                removed = market.product_prices.count()
                market.product_prices.all().delete()
            for key, value in values.items():
                setattr(market, key, value)
            market.save()
        # Only one default at a time.
        if is_default:
            Market.objects.exclude(pk=market.pk).update(is_default=False)
    # What a currency change took with it, for the caller to tell the merchant.
    market.removed_fixed_prices = removed
    market.removed_fixed_currency = old_currency if removed else ''
    return market


def removed_prices_note(market) -> str:
    """One sentence about fixed prices a currency change removed, or ''."""
    n = getattr(market, 'removed_fixed_prices', 0)
    if not n:
        return ''
    return (
        f'Removed {n} fixed price{"s" if n != 1 else ""} in {market.removed_fixed_currency}, '
        f'since the market now uses {market.currency}.'
    )


def delete_market(market) -> None:
    """Remove a market; its fixed product prices go with it."""
    market.delete()
