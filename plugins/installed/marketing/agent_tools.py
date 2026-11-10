"""Linda's coupon tools: list, create and change discount codes."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from morpheus.core import ToolError, ToolResult, tool

_TYPES = ['percentage', 'fixed_amount', 'free_shipping', 'buy_x_get_y']

_COUPON_FIELDS = {
    'name': {'type': 'string'},
    'description': {'type': 'string'},
    'discount_type': {'type': 'string', 'enum': _TYPES},
    'discount_value': {
        'type': 'number',
        'description': 'Percent, amount, or for buy_x_get_y the percent off the Y items (100 = free).',
    },
    'minimum_order_amount': {'type': 'number'},
    'maximum_discount_amount': {'type': 'number'},
    'usage_limit': {'type': 'integer'},
    'usage_limit_per_customer': {'type': 'integer'},
    'starts_at': {'type': 'string', 'description': 'ISO date-time.'},
    'expires_at': {'type': 'string', 'description': 'ISO date-time.'},
    'is_active': {'type': 'boolean'},
    'products': {
        'type': 'array',
        'items': {'type': 'string'},
        'description': 'SKUs or slugs. With categories and collections: the lines it discounts.',
    },
    'categories': {
        'type': 'array',
        'items': {'type': 'string'},
        'description': 'Category slugs; each covers the categories below it.',
    },
    'collections': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Slugs.'},
    'exclude_sale_items': {'type': 'boolean'},
    'buy_quantity': {'type': 'integer'},
    'get_quantity': {'type': 'integer'},
}


def _row(c) -> dict:
    return {
        'id': str(c.id),
        'code': c.code,
        'name': c.name,
        'discount_type': c.discount_type,
        'discount_value': str(c.discount_value),
        'is_active': c.is_active,
        'usable_now': c.is_valid,
        'times_used': c.times_used,
        'usage_limit': c.usage_limit,
        'starts_at': c.starts_at.isoformat() if c.starts_at else None,
        'expires_at': c.expires_at.isoformat() if c.expires_at else None,
        'products': [p.sku or p.slug for p in c.applicable_products.all()],
        'categories': list(c.applicable_categories.values_list('slug', flat=True)),
        'collections': list(c.applicable_collections.values_list('slug', flat=True)),
        'exclude_sale_items': c.exclude_sale_items,
        'buy_quantity': c.buy_quantity,
        'get_quantity': c.get_quantity,
    }


def _decimal(name, value) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ToolError(f'{name} must be a number.') from exc
    if number < 0:
        raise ToolError(f'{name} cannot be negative.')
    return number


def _when(name, value):
    from django.utils import timezone
    from django.utils.dateparse import parse_datetime

    if value in (None, ''):
        return None
    moment = parse_datetime(str(value))
    if moment is None:
        raise ToolError(f'{name} is not an ISO date-time.')
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment)
    return moment


def _lookup(model, values, label):
    from django.db.models import Q

    found, unknown = [], []
    for value in values or []:
        tok = str(value).strip()
        q = Q(slug=tok)
        if label == 'product':
            q |= Q(sku__iexact=tok) | Q(variants__sku__iexact=tok)
        row = model.objects.filter(q).distinct().first()
        if row is None:
            unknown.append(tok)
        else:
            found.append(row)
    if unknown:
        raise ToolError(f'No {label} with SKU or slug: {", ".join(unknown)}.')
    return found


def _apply(coupon, fields: dict) -> None:  # noqa: PLR0912 — one branch per field
    from djmoney.money import Money

    from plugins.dropshipping.importer import store_currency
    from plugins.installed.catalog.models import Category, Collection, Product

    currency = store_currency()
    for key in ('name', 'description'):
        if fields.get(key) is not None:
            setattr(coupon, key, str(fields[key]))
    if fields.get('discount_type') is not None:
        if fields['discount_type'] not in _TYPES:
            raise ToolError(f'discount_type must be one of {", ".join(_TYPES)}.')
        coupon.discount_type = fields['discount_type']
    if fields.get('discount_value') is not None:
        coupon.discount_value = _decimal('discount_value', fields['discount_value'])
    for key in ('minimum_order_amount', 'maximum_discount_amount'):
        if key in fields:
            value = fields[key]
            setattr(coupon, key, None if value is None else Money(_decimal(key, value), currency))
    for key in ('usage_limit', 'usage_limit_per_customer'):
        if key in fields:
            setattr(coupon, key, None if fields[key] is None else max(0, int(fields[key])))
    for key in ('starts_at', 'expires_at'):
        if key in fields:
            setattr(coupon, key, _when(key, fields[key]))
    for key in ('is_active', 'exclude_sale_items'):
        if fields.get(key) is not None:
            setattr(coupon, key, bool(fields[key]))
    for key in ('buy_quantity', 'get_quantity'):
        if fields.get(key) is not None:
            setattr(coupon, key, max(1, int(fields[key])))
    if coupon.discount_type == 'percentage' and coupon.discount_value > 100:
        raise ToolError('A percentage coupon cannot take off more than 100%.')
    if coupon.discount_type == 'buy_x_get_y' and coupon.discount_value > 100:
        raise ToolError(
            'For buy_x_get_y, discount_value is the percent off the Y items, up to 100.'
        )
    if coupon.discount_type in ('percentage', 'fixed_amount') and coupon.discount_value <= 0:
        raise ToolError('Give the coupon a discount_value above 0.')
    scope = {
        'products': _lookup(Product, fields['products'], 'product')
        if fields.get('products') is not None
        else None,
        'categories': _lookup(Category, fields['categories'], 'category')
        if fields.get('categories') is not None
        else None,
        'collections': _lookup(Collection, fields['collections'], 'collection')
        if fields.get('collections') is not None
        else None,
    }
    coupon.save()
    if scope['products'] is not None:
        coupon.applicable_products.set(scope['products'])
    if scope['categories'] is not None:
        coupon.applicable_categories.set(scope['categories'])
    if scope['collections'] is not None:
        coupon.applicable_collections.set(scope['collections'])


@tool(
    name='coupons.list',
    description='List discount codes with their type, limits, scope and how often each was used.',
    scopes=['promotions.read'],
    schema={'type': 'object', 'properties': {'active_only': {'type': 'boolean', 'default': False}}},
)
def list_coupons_tool(*, active_only: bool = False) -> ToolResult:
    from plugins.installed.marketing.models import Coupon

    qs = Coupon.objects.order_by('-created_at')
    if active_only:
        qs = qs.filter(is_active=True)
    rows = [_row(c) for c in qs[:200]]
    return ToolResult(output={'coupons': rows}, display=f'{len(rows)} coupon(s)')


@tool(
    name='coupons.create',
    description=(
        'Create a discount code a shopper types at checkout: percent or amount off, free '
        'shipping, or buy X get Y, optionally limited to products, categories or collections.'
    ),
    scopes=['promotions.write'],
    schema={
        'type': 'object',
        'properties': {'code': {'type': 'string'}, **_COUPON_FIELDS},
        'required': ['code', 'discount_type'],
    },
    requires_approval=True,
)
def create_coupon_tool(*, code: str, discount_type: str, **fields) -> ToolResult:
    from django.db import transaction

    from plugins.installed.marketing.models import Coupon

    code = (code or '').strip().upper()
    if not code:
        raise ToolError('Give the coupon a code.')
    if Coupon.objects.filter(code__iexact=code).exists():
        raise ToolError(f'Another coupon already uses the code {code}.')
    coupon = Coupon(code=code, name=str(fields.get('name') or code))
    with transaction.atomic():
        _apply(coupon, {**fields, 'discount_type': discount_type})
    return ToolResult(output=_row(coupon), display=f'Created coupon {coupon.code}')


@tool(
    name='coupons.update',
    description='Change a discount code: switch it off, extend it, change its discount, limits or scope. Only the fields given change.',
    scopes=['promotions.write'],
    schema={
        'type': 'object',
        'properties': {
            'code': {'type': 'string', 'description': 'The code to change.'},
            **_COUPON_FIELDS,
        },
        'required': ['code'],
    },
    requires_approval=True,
)
def update_coupon_tool(*, code: str, **fields) -> ToolResult:
    from django.db import transaction

    from plugins.installed.marketing.models import Coupon

    coupon = Coupon.objects.filter(code__iexact=(code or '').strip()).first()
    if coupon is None:
        raise ToolError(f'No coupon with the code {code}.')
    with transaction.atomic():
        _apply(coupon, fields)
    return ToolResult(output=_row(coupon), display=f'Saved coupon {coupon.code}')
