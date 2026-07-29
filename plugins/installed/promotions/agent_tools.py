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
            'channels': p.channels,
        }
        for p in qs.order_by('priority')[:200]
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
