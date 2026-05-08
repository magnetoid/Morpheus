"""Ecommerce read tools — give the Assistant first-class read access to
every commerce surface in the platform.

Each tool is read-only (`scopes=['system.read']`) and capped so a runaway
LLM call can't flood the conversation context. No write paths live here —
those route through the agent_core agents that already gate approval.

The tools are organised by domain:
  * orders.search / orders.get
  * products.search / products.get
  * customers.search / customers.get
  * analytics.summary / analytics.top_products
  * cms.pages
  * email.templates
  * settings.list
  * db.describe_model

Every tool uses lazy plugin imports so a missing plugin returns a clean
"plugin unavailable" message instead of breaking the Assistant.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from core.assistant.tools.filesystem import ToolError, ToolResult, tool


def _money_str(value: Any) -> str:
    """Convert a djmoney Money / Decimal / None into a flat string."""
    if value is None:
        return ''
    amount = getattr(value, 'amount', value)
    return str(amount)


def _money_amount(value: Any) -> Decimal:
    """Pull the numeric amount out of a Money / Decimal / numeric value."""
    if value is None:
        return Decimal('0')
    amount = getattr(value, 'amount', value)
    try:
        return Decimal(str(amount))
    except Exception:  # noqa: BLE001
        return Decimal('0')


# ── Orders ──────────────────────────────────────────────────────────────


@tool(
    name='orders.search',
    description=(
        'Search orders. Filter by status (pending/confirmed/processing/'
        'fulfilled/shipped/delivered/cancelled/refunded), date range '
        '(days_back), customer email substring, or order_number prefix. '
        'Returns up to `limit` orders, newest first.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'status': {'type': 'string'},
            'days_back': {'type': 'integer', 'minimum': 1, 'maximum': 365},
            'email': {'type': 'string'},
            'order_number': {'type': 'string'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
        },
    },
)
def orders_search_tool(*, status: str = '', days_back: int = 0,
                      email: str = '', order_number: str = '',
                      limit: int = 20) -> ToolResult:
    try:
        from django.utils import timezone
        from plugins.installed.orders.models import Order
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'orders plugin unavailable: {e}') from e
    qs = Order.objects.select_related('customer').all()
    if status:
        qs = qs.filter(status=status)
    if days_back:
        qs = qs.filter(placed_at__gte=timezone.now() - timedelta(days=int(days_back)))
    if email:
        qs = qs.filter(email__icontains=email)
    if order_number:
        qs = qs.filter(order_number__icontains=order_number)
    qs = qs.order_by('-placed_at')[: max(1, min(int(limit or 20), 50))]
    rows = [
        {
            'order_number': o.order_number,
            'status': o.status,
            'payment_status': getattr(o, 'payment_status', ''),
            'total': _money_str(getattr(o, 'total', None)),
            'currency': str(getattr(getattr(o, 'total', None), 'currency', '')),
            'email': o.email or getattr(o.customer, 'email', '') if o.customer_id else o.email,
            'placed_at': o.placed_at.isoformat() if o.placed_at else '',
        }
        for o in qs
    ]
    return ToolResult(output={'orders': rows, 'count': len(rows)},
                      display=f'{len(rows)} order(s)')


@tool(
    name='orders.get',
    description=(
        'Fetch a single order by `order_number` with line items, '
        'refunds, fulfillments, and customer info.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {'order_number': {'type': 'string'}},
        'required': ['order_number'],
    },
)
def orders_get_tool(*, order_number: str) -> ToolResult:
    try:
        from plugins.installed.orders.models import Order
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'orders plugin unavailable: {e}') from e
    try:
        o = (
            Order.objects
            .select_related('customer')
            .prefetch_related('items', 'refunds', 'fulfillments')
            .get(order_number=order_number)
        )
    except Order.DoesNotExist:
        raise ToolError(f'order not found: {order_number}')
    items = [
        {
            'name': i.product_name,
            'sku': i.sku,
            'quantity': i.quantity,
            'unit_price': _money_str(i.unit_price),
            'total_price': _money_str(i.total_price),
            'fulfilled_quantity': getattr(i, 'fulfilled_quantity', 0),
        }
        for i in o.items.all()
    ]
    refunds = [
        {
            'amount': _money_str(getattr(r, 'amount', None)),
            'reason': getattr(r, 'reason', ''),
            'created_at': r.created_at.isoformat() if getattr(r, 'created_at', None) else '',
        }
        for r in (getattr(o, 'refunds', None).all() if hasattr(o, 'refunds') else [])
    ]
    fulfillments = [
        {
            'state': getattr(f, 'state', ''),
            'tracking_number': getattr(f, 'tracking_number', ''),
            'carrier': getattr(f, 'carrier', ''),
            'created_at': f.created_at.isoformat() if getattr(f, 'created_at', None) else '',
        }
        for f in (getattr(o, 'fulfillments', None).all() if hasattr(o, 'fulfillments') else [])
    ]
    return ToolResult(output={
        'order_number': o.order_number,
        'status': o.status,
        'payment_status': getattr(o, 'payment_status', ''),
        'total': _money_str(getattr(o, 'total', None)),
        'subtotal': _money_str(getattr(o, 'subtotal', None)),
        'tax': _money_str(getattr(o, 'tax', None)),
        'shipping': _money_str(getattr(o, 'shipping', None)),
        'discount': _money_str(getattr(o, 'discount', None)),
        'currency': str(getattr(getattr(o, 'total', None), 'currency', '')),
        'email': o.email or (o.customer.email if o.customer_id else ''),
        'customer_id': str(o.customer_id) if o.customer_id else '',
        'placed_at': o.placed_at.isoformat() if o.placed_at else '',
        'notes': getattr(o, 'notes', '') or '',
        'items': items,
        'refunds': refunds,
        'fulfillments': fulfillments,
    })


# ── Products ────────────────────────────────────────────────────────────


@tool(
    name='products.search',
    description=(
        'Search products. Filter by status (active/draft/archived), name '
        '(substring), sku (substring), category slug or vendor slug. '
        'Returns up to `limit` products, newest first.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'status': {'type': 'string'},
            'name': {'type': 'string'},
            'sku': {'type': 'string'},
            'category': {'type': 'string'},
            'vendor': {'type': 'string'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
        },
    },
)
def products_search_tool(*, status: str = '', name: str = '', sku: str = '',
                        category: str = '', vendor: str = '',
                        limit: int = 20) -> ToolResult:
    try:
        from plugins.installed.catalog.models import Product
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'catalog plugin unavailable: {e}') from e
    qs = Product.objects.select_related('category', 'vendor').all()
    if status:
        qs = qs.filter(status=status)
    if name:
        qs = qs.filter(name__icontains=name)
    if sku:
        qs = qs.filter(sku__icontains=sku)
    if category:
        qs = qs.filter(category__slug__iexact=category) | qs.filter(category__name__icontains=category)
    if vendor:
        qs = qs.filter(vendor__slug__iexact=vendor) | qs.filter(vendor__name__icontains=vendor)
    qs = qs.order_by('-created_at')[: max(1, min(int(limit or 20), 50))]
    rows = [
        {
            'id': str(p.id),
            'name': p.name,
            'sku': p.sku or '',
            'slug': getattr(p, 'slug', ''),
            'status': p.status,
            'price': _money_str(getattr(p, 'price', None)),
            'currency': str(getattr(getattr(p, 'price', None), 'currency', '')),
            'category': getattr(p.category, 'name', '') if p.category_id else '',
            'vendor': getattr(p.vendor, 'name', '') if p.vendor_id else '',
            'product_type': getattr(p, 'product_type', ''),
        }
        for p in qs
    ]
    return ToolResult(output={'products': rows, 'count': len(rows)},
                      display=f'{len(rows)} product(s)')


@tool(
    name='products.get',
    description=(
        'Fetch one product by id, sku, or slug — whichever is passed. '
        'Returns the product with variants, images, and stock levels.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'sku': {'type': 'string'},
            'slug': {'type': 'string'},
        },
    },
)
def products_get_tool(*, id: str = '', sku: str = '', slug: str = '') -> ToolResult:
    try:
        from plugins.installed.catalog.models import Product
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'catalog plugin unavailable: {e}') from e
    qs = Product.objects.select_related('category', 'vendor').prefetch_related('variants', 'images')
    p = None
    try:
        if id:
            p = qs.filter(pk=id).first()
        if p is None and sku:
            p = qs.filter(sku=sku).first()
        if p is None and slug:
            p = qs.filter(slug=slug).first()
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'lookup failed: {e}') from e
    if p is None:
        raise ToolError('product not found — pass id, sku, or slug')

    variants = [
        {
            'id': str(v.id),
            'name': getattr(v, 'name', ''),
            'sku': getattr(v, 'sku', ''),
            'price': _money_str(getattr(v, 'price', None)),
            'attributes': getattr(v, 'attributes', None) or {},
        }
        for v in p.variants.all()
    ]
    images = [
        {
            'id': str(img.id),
            'url': getattr(getattr(img, 'image', None), 'url', '') if getattr(img, 'image', None) else '',
            'alt': getattr(img, 'alt', ''),
            'is_primary': getattr(img, 'is_primary', False),
        }
        for img in p.images.all()
    ]

    # Stock levels — optional inventory plugin.
    stock_levels: list[dict] = []
    try:
        from plugins.installed.inventory.models import StockLevel
        for sl in StockLevel.objects.filter(variant__product=p).select_related('variant', 'warehouse'):
            stock_levels.append({
                'variant_sku': getattr(sl.variant, 'sku', ''),
                'warehouse': getattr(sl.warehouse, 'name', '') if sl.warehouse_id else '',
                'on_hand': sl.quantity,
                'available': sl.available_quantity,
            })
    except Exception:  # noqa: BLE001
        pass

    return ToolResult(output={
        'id': str(p.id),
        'name': p.name,
        'sku': p.sku or '',
        'slug': getattr(p, 'slug', ''),
        'status': p.status,
        'price': _money_str(getattr(p, 'price', None)),
        'currency': str(getattr(getattr(p, 'price', None), 'currency', '')),
        'category': getattr(p.category, 'name', '') if p.category_id else '',
        'vendor': getattr(p.vendor, 'name', '') if p.vendor_id else '',
        'product_type': getattr(p, 'product_type', ''),
        'short_description': getattr(p, 'short_description', '')[:500],
        'description': getattr(p, 'description', '')[:2000],
        'meta_title': getattr(p, 'meta_title', ''),
        'meta_description': getattr(p, 'meta_description', ''),
        'variants': variants,
        'images': images,
        'stock_levels': stock_levels,
    })


# ── Customers ──────────────────────────────────────────────────────────


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
def customers_search_tool(*, email: str = '', name: str = '',
                         source: str = '', limit: int = 20) -> ToolResult:
    try:
        from django.contrib.auth import get_user_model
        from django.db.models import Q
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'auth unavailable: {e}') from e
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
            'last_order_at': (u.last_order_at.isoformat()
                              if getattr(u, 'last_order_at', None) else ''),
            'purchase_count': getattr(u, 'purchase_count', 0) or 0,
            'lifetime_value': _money_str(getattr(u, 'lifetime_value', None)),
        }
        for u in qs
    ]
    return ToolResult(output={'customers': rows, 'count': len(rows)},
                      display=f'{len(rows)} customer(s)')


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
    try:
        from django.contrib.auth import get_user_model
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'auth unavailable: {e}') from e
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
            addresses.append({
                'type': getattr(a, 'address_type', '') or getattr(a, 'type', ''),
                'line1': getattr(a, 'line1', '') or getattr(a, 'address1', ''),
                'line2': getattr(a, 'line2', '') or getattr(a, 'address2', ''),
                'city': getattr(a, 'city', ''),
                'country': getattr(a, 'country', ''),
                'postal_code': getattr(a, 'postal_code', '') or getattr(a, 'zip', ''),
                'is_default': getattr(a, 'is_default', False),
            })
    except Exception:  # noqa: BLE001
        pass

    recent_orders: list[dict] = []
    try:
        from plugins.installed.orders.models import Order
        for o in Order.objects.filter(customer=u).order_by('-placed_at')[:10]:
            recent_orders.append({
                'order_number': o.order_number,
                'status': o.status,
                'total': _money_str(getattr(o, 'total', None)),
                'placed_at': o.placed_at.isoformat() if o.placed_at else '',
            })
    except Exception:  # noqa: BLE001
        pass

    return ToolResult(output={
        'id': str(u.pk),
        'email': u.email,
        'first_name': getattr(u, 'first_name', ''),
        'last_name': getattr(u, 'last_name', ''),
        'is_staff': bool(getattr(u, 'is_staff', False)),
        'source': getattr(u, 'source', '') or '',
        'date_joined': u.date_joined.isoformat() if u.date_joined else '',
        'last_login': u.last_login.isoformat() if u.last_login else '',
        'last_order_at': (u.last_order_at.isoformat()
                          if getattr(u, 'last_order_at', None) else ''),
        'purchase_count': getattr(u, 'purchase_count', 0) or 0,
        'lifetime_value': _money_str(getattr(u, 'lifetime_value', None)),
        'addresses': addresses,
        'recent_orders': recent_orders,
    })


# ── Analytics ───────────────────────────────────────────────────────────


@tool(
    name='analytics.summary',
    description=(
        'Sales summary for the last `days_back` days: revenue, orders, '
        'AOV, new customers. Default 7 days. Use this before drilling '
        'into specifics — gives the LLM the right framing.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'days_back': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 7},
        },
    },
)
def analytics_summary_tool(*, days_back: int = 7) -> ToolResult:
    try:
        from django.contrib.auth import get_user_model
        from django.db.models import Sum, Count
        from django.utils import timezone
        from plugins.installed.orders.models import Order
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'orders/auth unavailable: {e}') from e
    days = max(1, min(int(days_back or 7), 365))
    since = timezone.now() - timedelta(days=days)
    prev_since = since - timedelta(days=days)
    cur = Order.objects.filter(placed_at__gte=since)
    prev = Order.objects.filter(placed_at__gte=prev_since, placed_at__lt=since)
    cur_count = cur.count()
    cur_rev = cur.aggregate(t=Sum('total'))['t'] or Decimal('0')
    prev_count = prev.count()
    prev_rev = prev.aggregate(t=Sum('total'))['t'] or Decimal('0')
    aov = (cur_rev / cur_count) if cur_count else Decimal('0')
    User = get_user_model()
    new_customers = User.objects.filter(date_joined__gte=since).count()

    def pct(now, before):
        if not before:
            return None
        return float(((Decimal(now) - Decimal(before)) / Decimal(before) * Decimal('100')).quantize(Decimal('0.01')))

    return ToolResult(output={
        'window_days': days,
        'orders': cur_count,
        'orders_prev': prev_count,
        'orders_pct_change': pct(cur_count, prev_count),
        'revenue': str(cur_rev),
        'revenue_prev': str(prev_rev),
        'revenue_pct_change': pct(cur_rev, prev_rev),
        'avg_order_value': str(aov),
        'new_customers': new_customers,
    })


@tool(
    name='analytics.top_products',
    description=(
        'Top-N products by revenue or units sold over the last `days_back` '
        'days. Default 30 days, sort by revenue.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'days_back': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 30},
            'by': {'type': 'string', 'enum': ['revenue', 'units'], 'default': 'revenue'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 10},
        },
    },
)
def analytics_top_products_tool(*, days_back: int = 30, by: str = 'revenue',
                               limit: int = 10) -> ToolResult:
    try:
        from django.db.models import Sum
        from django.utils import timezone
        from plugins.installed.orders.models import OrderItem
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'orders unavailable: {e}') from e
    days = max(1, min(int(days_back or 30), 365))
    since = timezone.now() - timedelta(days=days)
    qs = (
        OrderItem.objects
        .filter(order__placed_at__gte=since)
        .values('product_id', 'product_name')
        .annotate(units=Sum('quantity'), revenue=Sum('total_price'))
    )
    sort_key = '-revenue' if by != 'units' else '-units'
    qs = qs.order_by(sort_key)[: max(1, min(int(limit or 10), 50))]
    rows = [
        {
            'product_id': str(r['product_id']) if r['product_id'] else '',
            'name': r['product_name'] or '',
            'units': int(r['units'] or 0),
            'revenue': str(r['revenue'] or 0),
        }
        for r in qs
    ]
    return ToolResult(output={'window_days': days, 'sort': by, 'products': rows},
                      display=f'top {len(rows)} by {by}')


# ── Content (CMS + email templates) ─────────────────────────────────────


@tool(
    name='cms.pages',
    description='List CMS pages with title, slug, state, and updated date.',
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'state': {'type': 'string'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 50},
        },
    },
)
def cms_pages_tool(*, state: str = '', limit: int = 50) -> ToolResult:
    try:
        from plugins.installed.cms.models import Page
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'cms plugin unavailable: {e}') from e
    qs = Page.objects.all()
    if state:
        qs = qs.filter(state=state)
    qs = qs.order_by('-updated_at')[: max(1, min(int(limit or 50), 100))]
    rows = [
        {
            'id': str(p.pk),
            'title': getattr(p, 'title', ''),
            'slug': getattr(p, 'slug', ''),
            'state': getattr(p, 'state', ''),
            'updated_at': p.updated_at.isoformat() if getattr(p, 'updated_at', None) else '',
            'published_at': (p.published_at.isoformat()
                             if getattr(p, 'published_at', None) else ''),
        }
        for p in qs
    ]
    return ToolResult(output={'pages': rows, 'count': len(rows)},
                      display=f'{len(rows)} page(s)')


@tool(
    name='email.templates',
    description=(
        'List email templates: key, subject, whether the merchant has '
        'customised the default. Read-only — does not return body HTML '
        'because it can be very long; use db.find on EmailTemplate for '
        'a single full record.'
    ),
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}},
)
def email_templates_tool() -> ToolResult:
    try:
        from plugins.installed.cms.models import EmailTemplate
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'cms plugin unavailable: {e}') from e
    rows = [
        {
            'key': getattr(t, 'key', ''),
            'subject': getattr(t, 'subject', ''),
            'is_customised': bool(getattr(t, 'is_customised', False)),
            'updated_at': t.updated_at.isoformat() if getattr(t, 'updated_at', None) else '',
        }
        for t in EmailTemplate.objects.all().order_by('key')
    ]
    return ToolResult(output={'templates': rows, 'count': len(rows)})


# ── Settings / configuration ────────────────────────────────────────────


@tool(
    name='settings.list',
    description=(
        'List every plugin\'s stored config (read-only). Returns a flat '
        'dict keyed by plugin name. Useful for confirming what\'s '
        'enabled, what API keys are stored (redacted), and which '
        'feature flags are set.'
    ),
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}},
)
def settings_list_tool() -> ToolResult:
    try:
        from plugins.models import PluginConfig
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'plugins.models unavailable: {e}') from e
    out: dict[str, Any] = {}
    SECRET_KEYS = ('api_key', 'secret', 'password', 'token', 'webhook_secret')
    for cfg in PluginConfig.objects.all():
        data = dict(cfg.config_data or {})
        # Redact anything that looks like a secret.
        for k in list(data.keys()):
            lk = k.lower()
            if any(s in lk for s in SECRET_KEYS):
                v = data[k]
                if isinstance(v, str) and len(v) > 4:
                    data[k] = v[:2] + '…(redacted)…' + v[-2:]
                else:
                    data[k] = '(redacted)'
        out[cfg.plugin_name] = {
            'is_enabled': cfg.is_enabled,
            'config': data,
        }
    return ToolResult(output={'plugins': out, 'count': len(out)},
                      display=f'{len(out)} plugin config(s)')


# ── Media library ───────────────────────────────────────────────────────


@tool(
    name='media.search',
    description=(
        'Search the media library. Filter by kind (image/video/audio/'
        'document/other), filename substring, or tag. Returns up to '
        '`limit` assets, newest first.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'kind': {'type': 'string'},
            'filename': {'type': 'string'},
            'tag': {'type': 'string'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
        },
    },
)
def media_search_tool(*, kind: str = '', filename: str = '', tag: str = '',  # noqa: PLR0913
                     limit: int = 20) -> ToolResult:
    try:
        from plugins.installed.media.models import MediaAsset
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'media plugin unavailable: {e}') from e
    qs = MediaAsset.objects.all()
    if kind:
        qs = qs.filter(kind=kind)
    if filename:
        qs = qs.filter(filename__icontains=filename)
    if tag:
        qs = qs.filter(tags__contains=[tag])
    qs = qs.order_by('-created_at')[: max(1, min(int(limit or 20), 50))]
    rows = [
        {
            'id': str(a.id),
            'filename': a.filename,
            'kind': a.kind,
            'mime_type': a.mime_type,
            'size_bytes': a.size_bytes,
            'width': a.width,
            'height': a.height,
            'alt_text': a.alt_text,
            'tags': list(a.tags or []),
            'url': a.url,
        }
        for a in qs
    ]
    return ToolResult(output={'assets': rows, 'count': len(rows)},
                      display=f'{len(rows)} asset(s)')


# ── Metafields ──────────────────────────────────────────────────────────


@tool(
    name='metafields.list_for',
    description=(
        'List every metafield on a record. Pass `model` as '
        '`app_label.ModelName` and `object_id` (string pk). Returns a '
        'flat dict keyed by `namespace.key`.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'model': {'type': 'string'},
            'object_id': {'type': 'string'},
        },
        'required': ['model', 'object_id'],
    },
)
def metafields_list_for_tool(*, model: str, object_id: str) -> ToolResult:
    from django.apps import apps
    from django.contrib.contenttypes.models import ContentType
    try:
        from plugins.installed.metafields.models import Metafield
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'metafields plugin unavailable: {e}') from e
    try:
        app_label, model_name = model.split('.', 1)
        m = apps.get_model(app_label, model_name)
    except (ValueError, LookupError) as e:
        raise ToolError(f'unknown model: {model}') from e
    ct = ContentType.objects.get_for_model(m)
    rows = list(Metafield.objects.filter(content_type=ct, object_id=str(object_id)))
    return ToolResult(output={
        'model': f'{app_label}.{model_name}',
        'object_id': str(object_id),
        'metafields': [
            {
                'namespace': mf.namespace,
                'key': mf.key,
                'full_key': mf.full_key,
                'value': mf.value,
                'value_type': mf.value_type,
                'description': mf.description,
            }
            for mf in rows
        ],
    }, display=f'{len(rows)} metafield(s)')


# ── Markets ─────────────────────────────────────────────────────────────


@tool(
    name='markets.list',
    description=(
        'List configured Markets — region/code/currency/locale + active '
        'flag + per-market price adjustment. Use this to answer "where '
        'are we selling and at what currency?".'
    ),
    scopes=['system.read'],
    schema={'type': 'object', 'properties': {}},
)
def markets_list_tool() -> ToolResult:
    try:
        from plugins.installed.markets.models import Market
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'markets plugin unavailable: {e}') from e
    rows = [
        {
            'code': m.code,
            'label': m.label,
            'currency': m.currency,
            'locale': m.default_locale,
            'countries': list(m.country_codes or []),
            'price_adjustment_pct': str(m.base_price_adjustment_pct or 0),
            'is_active': m.is_active,
            'is_default': m.is_default,
        }
        for m in Market.objects.all()
    ]
    return ToolResult(output={'markets': rows, 'count': len(rows)},
                      display=f'{len(rows)} market(s)')


# ── Schema introspection ────────────────────────────────────────────────


@tool(
    name='db.describe_model',
    description=(
        'Return field schema for a Django model: `app_label.ModelName`. '
        'Use this when you need to know what fields are available before '
        'calling a more specific search tool.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {'model': {'type': 'string'}},
        'required': ['model'],
    },
)
def db_describe_model_tool(*, model: str) -> ToolResult:
    from django.apps import apps
    try:
        app_label, model_name = model.split('.', 1)
        m = apps.get_model(app_label, model_name)
    except (ValueError, LookupError) as e:
        raise ToolError(f'unknown model: {model}') from e
    fields = []
    for f in m._meta.get_fields():
        if f.auto_created and not getattr(f, 'concrete', False):
            # Skip reverse relations for brevity.
            continue
        fields.append({
            'name': f.name,
            'type': f.__class__.__name__,
            'null': getattr(f, 'null', False),
            'unique': getattr(f, 'unique', False),
            'help_text': str(getattr(f, 'help_text', '') or '')[:120],
        })
    return ToolResult(output={
        'model': f'{m._meta.app_label}.{m.__name__}',
        'verbose_name': str(m._meta.verbose_name),
        'table': m._meta.db_table,
        'fields': fields,
    }, display=f'{len(fields)} field(s)')
