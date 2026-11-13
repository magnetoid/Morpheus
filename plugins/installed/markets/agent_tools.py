"""Markets agent tools: read markets and rates, and change them with the merchant's yes.

markets.list was migrated here from core/assistant/tools/ecommerce.py so the
Market query lives in the plugin that owns it. Every change goes through the
same functions the dashboard uses (services.save_market / delete_market,
rates.set_manual_rate / fetch_ecb), so a refusal reads the same in both.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from morpheus.core import ToolError, ToolResult, tool


def _row(m) -> dict:
    return {
        'code': m.code,
        'label': m.label,
        'currency': m.currency,
        'locale': m.default_locale,
        'countries': list(m.country_codes or []),
        'price_adjustment_pct': str(m.base_price_adjustment_pct or 0),
        'rounding': m.rounding,
        'is_active': m.is_active,
        'is_default': m.is_default,
    }


def _market(code: str):
    from plugins.installed.markets.models import Market  # noqa: PLC0415

    market = Market.objects.filter(code=(code or '').strip().lower()).first()
    if market is None:
        raise ToolError(f'There is no market with the code "{code}".')
    return market


def _product(ref: str):
    import uuid  # noqa: PLC0415

    from plugins.installed.catalog.models import Product  # noqa: PLC0415

    ref = (ref or '').strip()
    product = Product.objects.filter(slug=ref).first()
    if product is None:
        try:
            product = Product.objects.filter(pk=uuid.UUID(ref)).first()
        except ValueError:
            product = None
    if product is None:
        raise ToolError(f'There is no product with the id or slug "{ref}".')
    return product


def _number(value, what: str) -> Decimal:
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ToolError(f'The {what} must be a number.') from None
    return number


def _text(error: ValidationError) -> str:
    return ' '.join(error.messages)


@tool(
    name='markets.list',
    description=(
        'List configured Markets: code, currency, locale, countries, price '
        'adjustment, rounding, and whether each is active or the default. Use '
        'this to answer "where are we selling and at what currency?".'
    ),
    scopes=['markets.read'],
    schema={'type': 'object', 'properties': {}},
)
def markets_list_tool() -> ToolResult:
    from plugins.installed.markets.models import Market  # noqa: PLC0415

    rows = [_row(m) for m in Market.objects.all()]
    return ToolResult(
        output={'markets': rows, 'count': len(rows)}, display=f'{len(rows)} market(s)'
    )


@tool(
    name='markets.get',
    description=(
        'One market by code: its settings, the exchange rate for its currency (where it came '
        'from, how old, whether it is out of date) and what five products cost there. '
        'Shoppers still see the store currency; these are the prices the market would show.'
    ),
    scopes=['markets.read'],
    schema={
        'type': 'object',
        'properties': {'code': {'type': 'string', 'description': 'The market code, like "eu"'}},
        'required': ['code'],
    },
)
def markets_get_tool(*, code: str) -> ToolResult:
    from core.pricing import store_currency  # noqa: PLC0415
    from plugins.installed.markets import rates  # noqa: PLC0415
    from plugins.installed.markets.pricing import preview  # noqa: PLC0415

    market = _market(code)
    currency = market.currency.upper()
    rate = None
    if currency != store_currency():
        row = rates.rate_row(currency)
        rate = {
            'from': store_currency(),
            'to': currency,
            'rate': str(row['rate']) if row['rate'] is not None else None,
            'source': row['source'],
            'fetched_at': row['fetched_at'].isoformat() if row['fetched_at'] else None,
            'out_of_date': row['stale'],
        }
    prices = [
        {
            'product': r['name'],
            'slug': r['slug'],
            'store_price': str(r['store_price']),
            'market_price': str(r['market_price']) if r['market_price'] is not None else None,
        }
        for r in preview(market, 5)
    ]
    return ToolResult(
        output={'market': _row(market), 'rate': rate, 'preview': prices},
        display=f'{market.label} ({currency})',
    )


_FIELDS = {
    'label': {'type': 'string'},
    'currency': {'type': 'string', 'description': 'ISO 4217 code, like EUR'},
    'country_codes': {
        'type': 'array',
        'items': {'type': 'string'},
        'description': 'Two-letter country codes, like ["DE", "FR"]',
    },
    'default_locale': {'type': 'string', 'description': 'Language code, like "en" or "de"'},
    'base_price_adjustment_pct': {
        'type': 'number',
        'description': 'Percent added to every price in this market, -90 to 500',
    },
    'rounding': {
        'type': 'string',
        'enum': ['exact', 'whole', 'ninety_nine'],
        'description': 'How a converted price is rounded',
    },
    'is_active': {'type': 'boolean'},
    'is_default': {'type': 'boolean'},
}


@tool(
    name='markets.save',
    description=(
        'Create a market, or change the one with that code. Only the fields you give change. '
        'A market in another currency can be switched on only once that currency has an '
        'exchange rate (markets.set_rate or markets.refresh_rates). Affects prices shoppers '
        'will see once markets go live.'
    ),
    scopes=['markets.write'],
    schema={
        'type': 'object',
        'properties': {
            'code': {'type': 'string', 'description': 'Letters, numbers and dashes, like "eu"'},
            **_FIELDS,
        },
        'required': ['code'],
    },
    requires_approval=True,
)
def markets_save_tool(*, code: str, **fields) -> ToolResult:
    from plugins.installed.markets.models import Market  # noqa: PLC0415
    from plugins.installed.markets.services import save_market  # noqa: PLC0415

    code = (code or '').strip().lower()
    market = Market.objects.filter(code=code).first()
    data = {k: v for k, v in fields.items() if k in _FIELDS and v is not None}
    data['code'] = code
    try:
        saved = save_market(data, market)
    except ValidationError as e:
        raise ToolError(_text(e)) from e
    return ToolResult(
        output={'market': _row(saved), 'created': market is None},
        display=f'{"Created" if market is None else "Updated"} market {saved.label}',
    )


@tool(
    name='markets.delete',
    description='Delete a market. The prices fixed for its products go with it.',
    scopes=['markets.write'],
    schema={
        'type': 'object',
        'properties': {'code': {'type': 'string'}},
        'required': ['code'],
    },
    requires_approval=True,
)
def markets_delete_tool(*, code: str) -> ToolResult:
    from plugins.installed.markets.services import delete_market  # noqa: PLC0415

    market = _market(code)
    label = market.label
    delete_market(market)
    return ToolResult(output={'deleted': code}, display=f'Deleted market {label}')


@tool(
    name='markets.set_product_price',
    description=(
        "Fix one product's price in a market, in the market's currency, or pass amount null to "
        'remove it so the converted price applies again. A fixed price is never rounded or '
        'adjusted. Not for a market in the store currency: change the product price instead.'
    ),
    scopes=['markets.write'],
    schema={
        'type': 'object',
        'properties': {
            'code': {'type': 'string', 'description': 'The market code'},
            'product': {'type': 'string', 'description': 'Product id or slug'},
            'amount': {
                'type': ['number', 'null'],
                'description': "Price in the market's currency; null removes the fixed price",
            },
        },
        'required': ['code', 'product', 'amount'],
    },
    requires_approval=True,
)
def markets_set_product_price_tool(*, code: str, product: str, amount=None) -> ToolResult:
    from djmoney.money import Money  # noqa: PLC0415

    from core.pricing import quantize, store_currency  # noqa: PLC0415
    from plugins.installed.markets.models import ProductMarketPrice  # noqa: PLC0415

    market = _market(code)
    item = _product(product)
    currency = market.currency.upper()
    if currency == store_currency():
        raise ToolError(
            f'This market uses {currency}, the store currency, so it shows the product price. '
            'Change the product price instead.'
        )
    if amount is None:
        ProductMarketPrice.objects.filter(market=market, product=item).delete()
        return ToolResult(
            output={'market': market.code, 'product': item.slug, 'fixed_price': None},
            display=f'Removed the fixed price of {item.name} in {market.label}',
        )
    value = _number(amount, 'price')
    if not value.is_finite() or value <= 0:
        raise ToolError('The price must be more than zero.')
    price = Money(quantize(value, currency), currency)
    ProductMarketPrice.objects.update_or_create(
        market=market, product=item, defaults={'price': price, 'is_visible': True}
    )
    return ToolResult(
        output={'market': market.code, 'product': item.slug, 'fixed_price': str(price)},
        display=f'{item.name} costs {price} in {market.label}',
    )


@tool(
    name='markets.set_rate',
    description=(
        'Set your own exchange rate: how many units of the currency one unit of the store '
        'currency buys. A rate you set is never replaced by the daily fetch. Pass rate null '
        'to remove yours and use the daily rate again. Affects prices shoppers will see.'
    ),
    scopes=['markets.write'],
    schema={
        'type': 'object',
        'properties': {
            'currency': {'type': 'string', 'description': 'ISO 4217 code, like EUR'},
            'rate': {'type': ['number', 'null'], 'description': 'Units per store-currency unit'},
        },
        'required': ['currency', 'rate'],
    },
    requires_approval=True,
)
def markets_set_rate_tool(*, currency: str, rate=None) -> ToolResult:
    from plugins.installed.markets import rates  # noqa: PLC0415

    value = None if rate is None else _number(rate, 'rate')
    try:
        rates.set_manual_rate(currency, value)
    except ValidationError as e:
        raise ToolError(_text(e)) from e
    code = currency.strip().upper()
    return ToolResult(
        output={'currency': code, 'rate': None if value is None else str(value)},
        display=f'Removed your rate for {code}' if value is None else f'Set {code} to {value}',
    )


@tool(
    name='markets.refresh_rates',
    description=(
        "Fetch the European Central Bank's exchange rates now. A rate you set yourself is kept."
    ),
    scopes=['markets.write'],
    schema={'type': 'object', 'properties': {}},
    requires_approval=True,
)
def markets_refresh_rates_tool() -> ToolResult:
    from plugins.installed.markets import rates  # noqa: PLC0415

    try:
        result = rates.fetch_ecb()
    except Exception as e:  # noqa: BLE001 — the merchant reads why
        raise ToolError(f'Could not fetch the rates just now: {e}') from e
    return ToolResult(
        output=result, display=f'Fetched {result["written"]} rates dated {result["date"]}'
    )
