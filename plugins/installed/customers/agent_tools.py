"""Customer read tools for the agent layer.

customers.search / customers.get were migrated here from
core/assistant/tools/ecommerce.py so the Customer (auth user) queries live in the
plugin that owns them. Tool names + scopes unchanged — Linda sources them by name
from the agent registry, so her prompts/skills keep resolving.
"""

from __future__ import annotations

from core.agents import ToolError, ToolResult, tool
from core.money import money_str as _money_str


@tool(
    name='customers.search',
    description=(
        'Search customers/contacts. Filter by email, name (first/last), '
        'or source (order/lead_form/signup/newsletter/etc). Newest first.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'name': {'type': 'string'},
            'source': {'type': 'string'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
        },
    },
)
def customers_search_tool(
    *, email: str = '', name: str = '', source: str = '', limit: int = 20
) -> ToolResult:
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    User = get_user_model()
    qs = User.objects.all()
    if email:
        qs = qs.filter(email__icontains=email)
    if name:
        qs = qs.filter(Q(first_name__icontains=name) | Q(last_name__icontains=name))
    if source:
        qs = qs.filter(source=source)
    qs = qs.order_by('-date_joined')[: max(1, min(int(limit or 20), 50))]
    rows = [
        {
            'id': str(u.pk),
            'email': u.email,
            'name': (f'{u.first_name} {u.last_name}'.strip() or '—'),
            'source': getattr(u, 'source', '') or '',
            'date_joined': u.date_joined.isoformat() if u.date_joined else '',
            'last_order_at': (
                u.last_order_at.isoformat() if getattr(u, 'last_order_at', None) else ''
            ),
            'purchase_count': getattr(u, 'purchase_count', 0) or 0,
            'lifetime_value': _money_str(getattr(u, 'lifetime_value', None)),
        }
        for u in qs
    ]
    return ToolResult(
        output={'customers': rows, 'count': len(rows)}, display=f'{len(rows)} customer(s)'
    )


@tool(
    name='customers.get',
    description=(
        'Fetch a single customer by id or email. Returns profile, '
        'order summary, addresses, and recent orders.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'email': {'type': 'string'},
        },
    },
)
def customers_get_tool(*, id: str = '', email: str = '') -> ToolResult:
    from django.contrib.auth import get_user_model

    User = get_user_model()
    u = None
    if id:
        u = User.objects.filter(pk=id).first()
    if u is None and email:
        u = User.objects.filter(email__iexact=email).first()
    if u is None:
        raise ToolError('customer not found — pass id or email')

    addresses: list[dict] = []
    try:
        for a in u.addresses.all():
            addresses.append(
                {
                    'type': getattr(a, 'address_type', '') or getattr(a, 'type', ''),
                    'line1': getattr(a, 'line1', '') or getattr(a, 'address1', ''),
                    'line2': getattr(a, 'line2', '') or getattr(a, 'address2', ''),
                    'city': getattr(a, 'city', ''),
                    'country': getattr(a, 'country', ''),
                    'postal_code': getattr(a, 'postal_code', '') or getattr(a, 'zip', ''),
                    'is_default': getattr(a, 'is_default', False),
                }
            )
    except Exception:  # noqa: BLE001, S110
        pass

    recent_orders: list[dict] = []
    try:
        from plugins.installed.orders.models import Order

        for o in Order.objects.filter(customer=u).order_by('-placed_at')[:10]:
            recent_orders.append(
                {
                    'order_number': o.order_number,
                    'status': o.status,
                    'total': _money_str(getattr(o, 'total', None)),
                    'placed_at': o.placed_at.isoformat() if o.placed_at else '',
                }
            )
    except Exception:  # noqa: BLE001, S110
        pass

    return ToolResult(
        output={
            'id': str(u.pk),
            'email': u.email,
            'first_name': getattr(u, 'first_name', ''),
            'last_name': getattr(u, 'last_name', ''),
            'is_staff': bool(getattr(u, 'is_staff', False)),
            'source': getattr(u, 'source', '') or '',
            'date_joined': u.date_joined.isoformat() if u.date_joined else '',
            'last_login': u.last_login.isoformat() if u.last_login else '',
            'last_order_at': (
                u.last_order_at.isoformat() if getattr(u, 'last_order_at', None) else ''
            ),
            'purchase_count': getattr(u, 'purchase_count', 0) or 0,
            'lifetime_value': _money_str(getattr(u, 'lifetime_value', None)),
            'addresses': addresses,
            'recent_orders': recent_orders,
        }
    )
