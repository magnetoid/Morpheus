"""Tax services — compute tax for a cart given an address.

How a line is taxed:

- A product or variant marked not taxable pays nothing.
- A product in a tax category pays that category's rates in the region, when the
  region has any; otherwise it pays the region's standard rates (no category).
- Every matching rate applies, in ``priority`` order. A compound rate is charged
  on the price plus the taxes before it (Quebec's QST, for instance).
- The base is what the shopper pays for the line: its price less its share of the
  cart's discounts. Gift cards, points and store credit pay the total later and
  never lower the base.
- Shipping is taxed at the region's standard rates when the store says so
  (``TaxConfiguration.shipping_taxable``).
- With ``prices_include_tax`` the prices already hold the tax, so the tax is the
  part of each price that is tax, and the shopper pays the price as shown.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from decimal import Decimal

from djmoney.money import Money

logger = logging.getLogger('morpheus.tax')

CENT = Decimal('0.01')


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


def _resolve_rates(region, category_code: str) -> list:
    """The rates a line pays in ``region``: its category's when the region has
    any for it, else the region's standard rates. Lowest priority first."""
    from plugins.installed.tax.models import TaxRate

    qs = TaxRate.objects.filter(region=region).order_by('priority', 'name')
    if category_code:
        rates = list(qs.filter(category_id=category_code))
        if rates:
            return rates
    return list(qs.filter(category__isnull=True))


def _fractions(rates: list) -> list[tuple]:
    """Each rate's tax per 1 of net price, compounding where a rate says so."""
    out = []
    taxes_so_far = Decimal('0')
    for rate in rates:
        base = Decimal('1') + taxes_so_far if rate.is_compound else Decimal('1')
        fraction = base * rate.fraction
        out.append((rate, fraction))
        taxes_so_far += fraction
    return out


def compute_tax(
    *,
    line_items: Iterable[dict],
    country: str = '',
    region: str = '',
    prices_include_tax: bool | None = None,
) -> dict:
    """Compute tax for a list of line items.

    Each line item: ``{'amount', 'currency', 'category_code' (optional), 'taxable'
    (optional, default True)}``, where ``amount`` is what the shopper pays for it.
    Returns ``{'total': Money, 'lines': [{'rate_name', 'rate_percent', 'amount':
    Money}], 'included': bool}``. ``included`` is True when the amounts already
    hold the tax: ``total`` is then the part of them that is tax, not an amount
    to add.

    ``total`` is ``Money(0)`` whenever no tax applies (no provider, no region, no
    rate); arithmetic on it is identity, so a caller never special-cases None.
    """
    from plugins.installed.tax.models import TaxConfiguration

    line_items = list(line_items)
    currency = next((i['currency'] for i in line_items if i.get('currency')), 'USD')
    config = TaxConfiguration.objects.first()
    if prices_include_tax is None:
        prices_include_tax = bool(config and config.prices_include_tax)
    empty = {'total': Money(Decimal('0'), currency), 'lines': [], 'included': prices_include_tax}
    if config and config.provider == 'none':
        return empty

    tax_region = _resolve_region(country, region)
    if not tax_region:
        logger.debug('tax: no region matched for country=%r region=%r', country, region)
        return empty

    by_rate: dict[str, dict] = {}
    rates_by_category: dict[str, list] = {}
    for item in line_items:
        if item.get('taxable') is False:
            continue
        amount = Decimal(str(item.get('amount', 0)))
        if amount <= 0:
            continue
        code = item.get('category_code') or ''
        if code not in rates_by_category:
            rates_by_category[code] = _fractions(_resolve_rates(tax_region, code))
        fractions = rates_by_category[code]
        if not fractions:
            continue
        net = amount
        if prices_include_tax:
            net = amount / (Decimal('1') + sum((f for _, f in fractions), Decimal('0')))
        for rate, fraction in fractions:
            entry = by_rate.setdefault(
                str(rate.id),
                {
                    'rate_name': rate.name,
                    'rate_percent': str(rate.rate_percent),
                    'amount': Decimal('0'),
                },
            )
            entry['amount'] += (net * fraction).quantize(CENT)

    lines = [
        {
            'rate_name': v['rate_name'],
            'rate_percent': v['rate_percent'],
            'amount': Money(v['amount'].quantize(CENT), currency),
        }
        for v in by_rate.values()
        if v['amount']
    ]
    total = sum((line['amount'].amount for line in lines), Decimal('0'))
    return {
        'total': Money(total.quantize(CENT), currency),
        'lines': lines,
        'included': prices_include_tax,
    }


def _category_codes(product_ids) -> dict:
    from plugins.installed.tax.models import ProductTaxCategory

    return dict(
        ProductTaxCategory.objects.filter(product_id__in=product_ids).values_list(
            'product_id', 'category_id'
        )
    )


def compute_tax_for_cart(
    cart,
    *,
    country: str = '',
    region: str = '',
    discount: Decimal | Money | None = None,
    shipping: Decimal | Money | None = None,
) -> dict:
    """Tax for a cart: each line less its share of ``discount``, plus
    ``shipping`` when the store taxes shipping."""
    from plugins.installed.tax.models import TaxConfiguration

    items = list(cart.items.select_related('product', 'variant').all())
    if not items:
        return compute_tax(line_items=[], country=country, region=region)
    currency = str(items[0].unit_price.currency)
    amounts = [Decimal(str(item.unit_price.amount)) * item.quantity for item in items]
    subtotal = sum(amounts, Decimal('0'))
    off = Decimal(str(getattr(discount, 'amount', discount) or 0))
    off = min(max(off, Decimal('0')), subtotal)
    codes = _category_codes({item.product_id for item in items})

    line_items = []
    for item, amount in zip(items, amounts, strict=True):
        share = (off * amount / subtotal) if subtotal else Decimal('0')
        variant = item.variant
        line_items.append(
            {
                'amount': amount - share,
                'currency': currency,
                'category_code': codes.get(item.product_id, ''),
                'taxable': bool(item.product.is_taxable)
                and (variant is None or bool(variant.is_taxable)),
            }
        )

    ship = Decimal(str(getattr(shipping, 'amount', shipping) or 0))
    config = TaxConfiguration.objects.first()
    if ship > 0 and config and config.shipping_taxable:
        line_items.append({'amount': ship, 'currency': currency})
    return compute_tax(line_items=line_items, country=country, region=region)


def set_product_category(product, code: str):
    """Put ``product`` in the tax category ``code``; an empty code takes it out,
    so it pays its region's standard rates. Raises ValueError on an unknown code."""
    from plugins.installed.tax.models import ProductTaxCategory, TaxCategory

    code = (code or '').strip()
    if not code:
        ProductTaxCategory.objects.filter(product=product).delete()
        return None
    category = TaxCategory.objects.filter(code=code).first()
    if category is None:
        raise ValueError(f'Unknown tax category: {code}')
    ProductTaxCategory.objects.update_or_create(product=product, defaults={'category': category})
    return category


def set_category(code: str, name: str, description: str = ''):
    """Create a tax category, or rename one. Returns ``(category, created)``."""
    from django.utils.text import slugify

    from plugins.installed.tax.models import TaxCategory

    code = slugify(code or name)[:64]
    name = (name or '').strip()[:120]
    if not code or not name:
        raise ValueError('A tax category needs a name.')
    return TaxCategory.objects.update_or_create(
        code=code, defaults={'name': name, 'description': (description or '').strip()}
    )


def update_settings(
    *,
    provider: str | None = None,
    prices_include_tax: bool | None = None,
    shipping_taxable: bool | None = None,
):
    """Change the store's tax settings; ``None`` leaves a setting as it is."""
    from plugins.installed.tax.models import TaxConfiguration

    config = TaxConfiguration.objects.first() or TaxConfiguration()
    if provider is not None:
        if provider not in ('local', 'none'):
            raise ValueError('provider must be "local" or "none".')
        config.provider = provider
    if prices_include_tax is not None:
        config.prices_include_tax = bool(prices_include_tax)
    if shipping_taxable is not None:
        config.shipping_taxable = bool(shipping_taxable)
    config.save()
    return config


def delete_category(code: str) -> bool:
    """Delete a tax category with its rates; its products go back to the standard
    rates. The rates go first: ``TaxRate.category`` is SET_NULL, which would turn
    a reduced rate into one more standard rate that every product pays."""
    from django.db import transaction

    from plugins.installed.tax.models import TaxCategory, TaxRate

    with transaction.atomic():
        TaxRate.objects.filter(category_id=code).delete()
        deleted, _ = TaxCategory.objects.filter(code=code).delete()
    return bool(deleted)
