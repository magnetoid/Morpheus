"""Tax services — compute tax for a cart given an address."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from decimal import Decimal

from djmoney.money import Money

logger = logging.getLogger('morpheus.tax')


def _resolve_region(country: str, region: str) -> TaxRegion | None:  # noqa: F821
    """Find the most specific matching region, falling back to country-only."""
    from plugins.installed.tax.models import TaxConfiguration, TaxRegion

    country = (country or '').strip().upper()[:2]
    region = (region or '').strip().upper()[:10]
    if not country:
        config = TaxConfiguration.objects.first()
        return config.default_region if config else None

    if region:
        match = TaxRegion.objects.filter(country=country, region__iexact=region).first()
        if match:
            return match
    return TaxRegion.objects.filter(country=country, region='').first()


def _resolve_rate(region, category_code: str) -> TaxRate | None:  # noqa: F821
    from plugins.installed.tax.models import TaxRate

    qs = TaxRate.objects.filter(region=region)
    if category_code:
        cat = qs.filter(category_id=category_code).first()
        if cat:
            return cat
    return qs.filter(category__isnull=True).first()


def compute_tax(*, line_items: Iterable[dict], country: str = '', region: str = '') -> dict:
    """Compute tax for a list of line items.

    Each line item: {'amount': Decimal|str, 'currency': str, 'category_code': str (optional)}.
    Returns: {'total': Money, 'lines': [{'rate_name', 'rate_percent', 'amount': Money}]}.

    Always returns ``Money(0, <currency>)`` for ``total`` when tax can't
    be computed (no provider, missing region, no rate). Previously this
    returned ``None`` and downstream `if total is None` checks were
    inconsistent — some treated it as zero, others crashed on arithmetic.
    """
    from plugins.installed.tax.models import TaxConfiguration

    # Use first line's currency as the zero-money currency, default USD.
    fallback_currency = 'USD'
    for item in line_items:
        cur = item.get('currency')
        if cur:
            fallback_currency = cur
            break
    zero = lambda: Money(Decimal('0'), fallback_currency)  # noqa: E731

    config = TaxConfiguration.objects.first()
    if config and config.provider == 'none':
        return {'total': zero(), 'lines': []}

    tax_region = _resolve_region(country, region)
    if not tax_region:
        logger.debug('tax: no region matched for country=%r region=%r', country, region)
        return {'total': zero(), 'lines': []}

    by_rate: dict[str, dict] = {}
    currency: str | None = None
    for item in line_items:
        amount = Decimal(str(item.get('amount', 0)))
        currency = currency or item.get('currency') or 'USD'
        rate = _resolve_rate(tax_region, item.get('category_code', ''))
        if rate is None or amount <= 0:
            continue
        tax_amt = (amount * rate.fraction).quantize(Decimal('0.01'))
        existing = by_rate.setdefault(
            str(rate.id),
            {
                'rate_name': rate.name,
                'rate_percent': str(rate.rate_percent),
                'amount': Decimal('0'),
            },
        )
        existing['amount'] += tax_amt

    lines = []
    total = Decimal('0')
    for v in by_rate.values():
        amt = v['amount'].quantize(Decimal('0.01'))
        total += amt
        lines.append(
            {
                'rate_name': v['rate_name'],
                'rate_percent': v['rate_percent'],
                'amount': Money(amt, currency or 'USD'),
            }
        )
    # Always return a Money — never None. The previous code returned
    # None when no tax lines matched, which forced every caller to
    # special-case it; a caller that forgot the None-check silently
    # undercharged. Money(0) is the unambiguous "no tax applies" value
    # and arithmetic on it is identity.
    return {
        'total': Money(total.quantize(Decimal('0.01')), currency or 'USD'),
        'lines': lines,
    }


def compute_tax_for_cart(cart, *, country: str = '', region: str = '') -> dict:
    """Convenience wrapper: pull line items off a Cart."""
    items = []
    for item in cart.items.select_related('product').all():
        category_code = ''
        product = item.product
        if hasattr(product, 'tax_category_code'):
            category_code = getattr(product, 'tax_category_code', '') or ''
        amount = Decimal(item.unit_price.amount) * item.quantity
        items.append(
            {
                'amount': amount,
                'currency': str(item.unit_price.currency),
                'category_code': category_code,
            }
        )
    return compute_tax(line_items=items, country=country, region=region)
