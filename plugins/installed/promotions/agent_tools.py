"""Agent tools for the promotions engine."""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


@tool(
    name='promotions.list',
    description='List active promotions with usage and channel scope.',
    scopes=['promotions.read'],
    schema={'type': 'object', 'properties': {'active_only': {'type': 'boolean', 'default': True}}},
)
def list_promotions_tool(*, active_only: bool = True) -> ToolResult:
    from plugins.installed.promotions.models import Promotion

    qs = Promotion.objects.all()
    if active_only:
        qs = qs.filter(is_active=True)
    rows = [
        {
            'id': str(p.id),
            'name': p.name,
            'slug': p.slug,
            'type': p.type,
            'priority': p.priority,
            'times_used': p.times_used,
            'usage_limit': p.usage_limit,
            'channels': p.channels,
            'is_active': p.is_active,
            'combinable': p.combinable,
            'starts_at': p.starts_at.isoformat() if p.starts_at else None,
            'ends_at': p.ends_at.isoformat() if p.ends_at else None,
            'requires_coupon': p.requires_coupon,
            'rules': [{'action': r.action, 'predicates': r.predicates} for r in p.rules.all()],
        }
        for p in qs.prefetch_related('rules').order_by('priority')[:200]
    ]
    return ToolResult(output={'promotions': rows}, display=f'{len(rows)} promotion(s)')


@tool(
    name='promotions.create_percent_off',
    description='Create a single-rule percent-off promotion (cart-level).',
    scopes=['promotions.write'],
    schema={
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'slug': {'type': 'string'},
            'percent_off': {'type': 'number'},
            'min_subtotal': {'type': 'number', 'default': 0},
            'channels': {'type': 'array', 'items': {'type': 'string'}, 'default': []},
            'priority': {'type': 'integer', 'default': 100},
        },
        'required': ['name', 'slug', 'percent_off'],
    },
    requires_approval=True,
)
def create_percent_off_tool(
    *,
    name: str,
    slug: str,
    percent_off: float,
    min_subtotal: float = 0,
    channels: list[str] | None = None,
    priority: int = 100,
) -> ToolResult:
    from plugins.installed.promotions.models import Promotion, PromotionRule

    if Promotion.objects.filter(slug=slug).exists():
        raise ToolError(f'Promotion slug already exists: {slug}')
    promo = Promotion.objects.create(
        name=name,
        slug=slug,
        type=Promotion.TYPE_ORDER,
        priority=priority,
        channels=list(channels or []),
    )
    PromotionRule.objects.create(
        promotion=promo,
        predicates={'min_subtotal': float(min_subtotal)} if min_subtotal else {},
        action={'kind': 'percent_off', 'value': float(percent_off)},
    )
    return ToolResult(
        output={'id': str(promo.id), 'slug': promo.slug, 'name': promo.name},
        display=f'Created promotion "{name}" — {percent_off}% off',
    )


_PROMOTION_FIELDS = {
    'slug': {'type': 'string', 'description': 'Made from the name when left out.'},
    'description': {'type': 'string'},
    'kind': {
        'type': 'string',
        'enum': ['percent_off', 'fixed_off', 'free_shipping', 'gift', 'bogo', 'tiered'],
        'description': 'gift adds one free product; bogo is buy X get Y; tiered is buy more, save more.',
    },
    'value': {
        'type': 'number',
        'description': 'Percent (percent_off), amount (fixed_off), or percent off the Y items (bogo; empty = free).',
    },
    'buy_qty': {'type': 'integer', 'description': 'bogo: units to buy.'},
    'free_qty': {'type': 'integer', 'description': 'bogo: units that get the discount.'},
    'gift_product': {'type': 'string', 'description': 'gift: SKU or slug of the free product.'},
    'tiers': {'type': 'string', 'description': 'tiered: "items:percent" pairs, e.g. "3:10, 5:15".'},
    'min_subtotal': {'type': 'number'},
    'max_subtotal': {'type': 'number'},
    'countries': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Two-letter codes.'},
    'customer_groups': {'type': 'array', 'items': {'type': 'string'}},
    'products': {
        'type': 'array',
        'items': {'type': 'string'},
        'description': 'SKUs or slugs: the cart must hold one (bogo: the products it counts).',
    },
    'categories': {
        'type': 'array',
        'items': {'type': 'string'},
        'description': 'Category slugs; each covers the categories below it.',
    },
    'first_order': {'type': 'boolean', 'description': 'A signed-in customer with no order yet.'},
    'priority': {'type': 'integer', 'description': 'Lower runs first. Default 100.'},
    'combinable': {
        'type': 'boolean',
        'description': 'False: applies only alone, never with another promotion or a coupon.',
    },
    'starts_at': {'type': 'string', 'description': 'ISO date-time, store time.'},
    'ends_at': {'type': 'string', 'description': 'ISO date-time, store time.'},
    'requires_coupon': {'type': 'string', 'description': 'Applies only with this code.'},
    'usage_limit': {'type': 'integer'},
    'is_active': {'type': 'boolean'},
}


def _form_data(base: dict, fields: dict) -> dict:
    """Tool arguments in the dashboard form's shape, so both share one
    validation (``promotions/forms.py``)."""
    data = {k: v for k, v in base.items() if v not in (None, '', [])}
    for key, val in fields.items():
        if val is None:
            continue
        if key in ('countries', 'customer_groups', 'products'):
            data[key] = ', '.join(str(v) for v in val)
        elif key == 'categories':
            data[key] = [str(v) for v in val]
        elif isinstance(val, bool):
            data[key] = 'on' if val else ''
        else:
            data[key] = str(val)
    for flag in ('is_active', 'combinable', 'first_order'):
        if data.get(flag) is True:
            data[flag] = 'on'
        elif data.get(flag) in (False, ''):
            data.pop(flag, None)
    return data


def _save(form) -> ToolResult:
    if not form.is_valid():
        errors = '; '.join(f'{k}: {" ".join(v)}' for k, v in form.errors.items())
        raise ToolError(f'Promotion not saved. {errors}')
    promo = form.save()
    rule = promo.rules.first()
    return ToolResult(
        output={
            'id': str(promo.id),
            'slug': promo.slug,
            'name': promo.name,
            'is_active': promo.is_active,
            'combinable': promo.combinable,
            'action': rule.action if rule else {},
            'predicates': rule.predicates if rule else {},
        },
        display=f'Saved promotion "{promo.name}"',
    )


@tool(
    name='promotions.create',
    description=(
        'Create an automatic promotion: percent or amount off, free shipping, a free gift, '
        'buy X get Y, or buy more save more, with optional conditions (cart size, products, '
        'categories, countries, customer groups, first order) and a schedule.'
    ),
    scopes=['promotions.write'],
    schema={
        'type': 'object',
        'properties': {'name': {'type': 'string'}, **_PROMOTION_FIELDS},
        'required': ['name', 'kind'],
    },
    requires_approval=True,
)
def create_promotion_tool(*, name: str, kind: str, **fields) -> ToolResult:
    from plugins.installed.promotions.forms import PromotionForm

    defaults = {'priority': 100, 'is_active': True, 'combinable': True}
    data = _form_data({}, {**defaults, **fields, 'name': name, 'kind': kind})
    return _save(PromotionForm(data))


@tool(
    name='promotions.update',
    description=(
        'Change a promotion: switch it on or off, reschedule it, or change its discount or '
        'conditions. Only the fields given change. Edits the first rule of the promotion.'
    ),
    scopes=['promotions.write'],
    schema={
        'type': 'object',
        'properties': {
            'promotion': {'type': 'string', 'description': 'The promotion id or slug.'},
            'name': {'type': 'string'},
            **_PROMOTION_FIELDS,
        },
        'required': ['promotion'],
    },
    requires_approval=True,
)
def update_promotion_tool(*, promotion: str, **fields) -> ToolResult:
    from plugins.installed.promotions.forms import PromotionForm
    from plugins.installed.promotions.models import Promotion

    promo = Promotion.objects.filter(slug=promotion).first()
    if promo is None:
        try:
            promo = Promotion.objects.filter(pk=promotion).first()
        except Exception:  # noqa: BLE001 — not a UUID
            promo = None
    if promo is None:
        raise ToolError(f'No promotion with id or slug "{promotion}".')
    current = PromotionForm(instance=promo).initial
    data = _form_data(current, fields)
    return _save(PromotionForm(data, instance=promo))
