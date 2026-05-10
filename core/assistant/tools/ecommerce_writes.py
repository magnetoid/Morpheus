"""Ecommerce write tools — turn the Assistant into a real operator.

Each write tool is gated by an explicit ``confirmed: bool`` argument so
the LLM cannot mutate state without first asking the user and getting
a "yes". The pattern is:

  1. LLM calls the tool with ``confirmed=False`` (or omits it).
  2. Tool returns an error: ``"requires explicit user confirmation"``.
  3. LLM tells the user what it's about to do, asks for confirmation.
  4. User says "yes" → LLM re-calls with ``confirmed=True``.
  5. Tool executes.

In addition every tool is marked ``requires_approval=True`` so the
agent_core runtime (which does have a real approval flow) gates them
when invoked from there.

Read tools live in `ecommerce.py` next door; nothing in this file
returns large result sets.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from core.assistant.tools.filesystem import ToolError, ToolResult, tool


_NEEDS_CONFIRM = (
    'this is a write operation — re-call with `confirmed=True` once the '
    'user has explicitly approved.'
)
_NEEDS_HARD_GATE = (
    'this action is destructive — after the user approves once, you must '
    'ALSO pass `hard_gate_ack="YES"` AND ask the user to type the affected '
    'name back to you. Both must match before re-calling.'
)


def _require_confirmed(confirmed: bool) -> None:
    if not confirmed:
        raise ToolError(_NEEDS_CONFIRM)


def _require_hard_gate(*, hard_gate_ack: str, target_name: str,
                       echo: str) -> None:
    """Enforce the second-tier confirmation for destructive actions.

    The LLM must collect both:
      * ``hard_gate_ack="YES"`` — the magic acknowledgement string.
      * ``echo`` — the user's typed-back identifier (must match
        ``target_name`` case-insensitively).
    A row is written to ``AgentApprovalRequest`` for the audit trail.
    """
    if (hard_gate_ack or '').strip().upper() != 'YES':
        raise ToolError(_NEEDS_HARD_GATE)
    if (echo or '').strip().lower() != (target_name or '').strip().lower():
        raise ToolError(
            f'echo mismatch — user typed {echo!r} but the target is {target_name!r}.'
        )
    try:
        from plugins.installed.agent_core.models import AgentApprovalRequest
        AgentApprovalRequest.objects.create(
            agent_name='assistant', state='approved',
            payload={'tool_target': target_name, 'echo': echo},
        )
    except Exception:  # noqa: BLE001 — audit row is best-effort
        pass


# ── Orders ──────────────────────────────────────────────────────────────


@tool(
    name='orders.update_status',
    description=(
        'Transition an order to a new status. Pass `order_number`, '
        '`status` (one of: pending, confirmed, processing, fulfilled, '
        'shipped, delivered, cancelled, refunded), and `confirmed=True` '
        'after the user has approved.'
    ),
    scopes=['orders.write'],
    schema={
        'type': 'object',
        'properties': {
            'order_number': {'type': 'string'},
            'status': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
        },
        'required': ['order_number', 'status'],
    },
    requires_approval=True,
)
def orders_update_status_tool(*, order_number: str, status: str,
                              confirmed: bool = False) -> ToolResult:
    _require_confirmed(confirmed)
    try:
        from plugins.installed.orders.models import Order
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'orders plugin unavailable: {e}') from e
    try:
        o = Order.objects.get(order_number=order_number)
    except Order.DoesNotExist:
        raise ToolError(f'order not found: {order_number}')
    prev = o.status
    o.status = status
    try:
        o.save(update_fields=['status', 'updated_at'])
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'save failed: {e}') from e
    return ToolResult(output={
        'order_number': order_number,
        'previous_status': prev,
        'new_status': status,
    }, display=f'#{order_number}: {prev} → {status}')


@tool(
    name='orders.cancel',
    description=(
        'Cancel an order. Sets status to `cancelled` and records the '
        'reason. Requires `confirmed=True`.'
    ),
    scopes=['orders.write'],
    schema={
        'type': 'object',
        'properties': {
            'order_number': {'type': 'string'},
            'reason': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
        },
        'required': ['order_number'],
    },
    requires_approval=True,
)
def orders_cancel_tool(*, order_number: str, reason: str = '',
                       confirmed: bool = False) -> ToolResult:
    _require_confirmed(confirmed)
    try:
        from plugins.installed.orders.models import Order, OrderEvent
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'orders plugin unavailable: {e}') from e
    try:
        o = Order.objects.get(order_number=order_number)
    except Order.DoesNotExist:
        raise ToolError(f'order not found: {order_number}')
    if o.status in ('cancelled', 'refunded'):
        raise ToolError(f'already {o.status}')
    prev = o.status
    o.status = 'cancelled'
    o.save(update_fields=['status', 'updated_at'])
    try:
        OrderEvent.objects.create(
            order=o, event_type='cancelled',
            message=f'Cancelled by Assistant. Reason: {reason or "(none)"}',
        )
    except Exception:  # noqa: BLE001
        pass
    return ToolResult(output={
        'order_number': order_number,
        'previous_status': prev,
        'new_status': 'cancelled',
        'reason': reason,
    }, display=f'#{order_number} cancelled')


@tool(
    name='orders.add_note',
    description=(
        'Append a note to an order (visible to staff, not the customer). '
        'Requires `confirmed=True`.'
    ),
    scopes=['orders.write'],
    schema={
        'type': 'object',
        'properties': {
            'order_number': {'type': 'string'},
            'note': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
        },
        'required': ['order_number', 'note'],
    },
    requires_approval=True,
)
def orders_add_note_tool(*, order_number: str, note: str,
                         confirmed: bool = False) -> ToolResult:
    _require_confirmed(confirmed)
    try:
        from plugins.installed.orders.models import Order
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'orders plugin unavailable: {e}') from e
    if not note.strip():
        raise ToolError('note cannot be empty')
    try:
        o = Order.objects.get(order_number=order_number)
    except Order.DoesNotExist:
        raise ToolError(f'order not found: {order_number}')
    existing = (getattr(o, 'notes', '') or '').strip()
    sep = '\n\n' if existing else ''
    o.notes = f'{existing}{sep}{note.strip()}'
    o.save(update_fields=['notes', 'updated_at'])
    return ToolResult(output={'order_number': order_number, 'appended': True},
                      display=f'note added to #{order_number}')


# ── Products ────────────────────────────────────────────────────────────


@tool(
    name='products.update_status',
    description=(
        'Set a product\'s status: active, draft, or archived. '
        'Pass either `id`, `sku`, or `slug` to identify the product.'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'sku': {'type': 'string'},
            'slug': {'type': 'string'},
            'status': {'type': 'string', 'enum': ['active', 'draft', 'archived']},
            'confirmed': {'type': 'boolean', 'default': False},
        },
        'required': ['status'],
    },
    requires_approval=True,
)
def products_update_status_tool(*, status: str, id: str = '', sku: str = '',
                                slug: str = '', confirmed: bool = False) -> ToolResult:
    _require_confirmed(confirmed)
    if status not in ('active', 'draft', 'archived'):
        raise ToolError(f'invalid status: {status}')
    try:
        from plugins.installed.catalog.models import Product
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'catalog plugin unavailable: {e}') from e
    p = None
    if id:
        p = Product.objects.filter(pk=id).first()
    if p is None and sku:
        p = Product.objects.filter(sku=sku).first()
    if p is None and slug:
        p = Product.objects.filter(slug=slug).first()
    if p is None:
        raise ToolError('product not found — pass id, sku, or slug')
    prev = p.status
    p.status = status
    p.save(update_fields=['status', 'updated_at'])
    return ToolResult(output={
        'product_id': str(p.id),
        'name': p.name,
        'previous_status': prev,
        'new_status': status,
    }, display=f'{p.name}: {prev} → {status}')


@tool(
    name='products.update_price',
    description=(
        'Update a product\'s price (optionally on a specific variant). '
        'Pass `id`/`sku`/`slug` to find the product, optional '
        '`variant_id` for a variant-specific change, and the new '
        '`price` as a numeric string ("19.99"). Currency stays the '
        'same. Requires `confirmed=True`.'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'sku': {'type': 'string'},
            'slug': {'type': 'string'},
            'variant_id': {'type': 'string'},
            'price': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
        },
        'required': ['price'],
    },
    requires_approval=True,
)
def products_update_price_tool(*, price: str, id: str = '', sku: str = '',
                               slug: str = '', variant_id: str = '',
                               confirmed: bool = False) -> ToolResult:
    _require_confirmed(confirmed)
    try:
        amount = Decimal(str(price))
    except (InvalidOperation, ValueError) as e:
        raise ToolError(f'invalid price: {price}') from e
    if amount < 0:
        raise ToolError('price cannot be negative')

    try:
        from plugins.installed.catalog.models import Product, ProductVariant
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'catalog plugin unavailable: {e}') from e

    if variant_id:
        v = ProductVariant.objects.filter(pk=variant_id).first()
        if v is None:
            raise ToolError(f'variant not found: {variant_id}')
        prev = str(getattr(getattr(v, 'price', None), 'amount', ''))
        # djmoney accepts a Decimal directly when assigned; the field's
        # currency is preserved from the existing value.
        v.price = amount
        v.save(update_fields=['price', 'updated_at'])
        return ToolResult(output={
            'variant_id': str(v.id), 'sku': v.sku,
            'previous_price': prev, 'new_price': str(amount),
        }, display=f'variant {v.sku}: {prev} → {amount}')

    p = None
    if id:
        p = Product.objects.filter(pk=id).first()
    if p is None and sku:
        p = Product.objects.filter(sku=sku).first()
    if p is None and slug:
        p = Product.objects.filter(slug=slug).first()
    if p is None:
        raise ToolError('product not found — pass id, sku, slug, or variant_id')
    prev = str(getattr(getattr(p, 'price', None), 'amount', ''))
    p.price = amount
    p.save(update_fields=['price', 'updated_at'])
    return ToolResult(output={
        'product_id': str(p.id), 'name': p.name,
        'previous_price': prev, 'new_price': str(amount),
    }, display=f'{p.name}: {prev} → {amount}')


# ── Customers ──────────────────────────────────────────────────────────


@tool(
    name='customers.add_note',
    description=(
        'Append an internal note to a customer record. Pass either '
        '`id` or `email`. Requires `confirmed=True`.'
    ),
    scopes=['customers.write'],
    schema={
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'email': {'type': 'string'},
            'note': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
        },
        'required': ['note'],
    },
    requires_approval=True,
)
def customers_add_note_tool(*, note: str, id: str = '', email: str = '',
                            confirmed: bool = False) -> ToolResult:
    _require_confirmed(confirmed)
    if not note.strip():
        raise ToolError('note cannot be empty')
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
    if not hasattr(u, 'notes'):
        raise ToolError('customer model has no `notes` field')
    existing = (getattr(u, 'notes', '') or '').strip()
    sep = '\n\n' if existing else ''
    u.notes = f'{existing}{sep}{note.strip()}'
    u.save(update_fields=['notes'])
    return ToolResult(output={'customer_id': str(u.pk), 'email': u.email,
                              'appended': True},
                      display=f'note added to {u.email}')


# ── Metafields ─────────────────────────────────────────────────────────


@tool(
    name='metafields.set',
    description=(
        'Set or update a metafield on a record. Pass `model` as '
        '`app_label.ModelName`, `object_id` (string pk), `namespace` '
        '(optional, defaults to ""), `key`, `value`, and an optional '
        '`value_type` hint (string/integer/number/boolean/json/date/'
        'url/email/file_id). Idempotent — re-setting the same '
        '`(model, object_id, namespace, key)` overwrites.'
    ),
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'model': {'type': 'string'},
            'object_id': {'type': 'string'},
            'namespace': {'type': 'string', 'default': ''},
            'key': {'type': 'string'},
            'value': {'type': 'string'},
            'value_type': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
        },
        'required': ['model', 'object_id', 'key', 'value'],
    },
    requires_approval=True,
)
def metafields_set_tool(*, model: str, object_id: str, key: str, value: str,
                        namespace: str = '', value_type: str = 'string',
                        confirmed: bool = False) -> ToolResult:
    _require_confirmed(confirmed)
    from django.apps import apps
    try:
        from plugins.installed.metafields.models import Metafield
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'metafields plugin unavailable: {e}') from e
    try:
        app_label, model_name = model.split('.', 1)
        m = apps.get_model(app_label, model_name)
    except (ValueError, LookupError) as e:
        raise ToolError(f'unknown model: {model}') from e
    instance = m.objects.filter(pk=object_id).first()
    if instance is None:
        raise ToolError(f'{model} not found: {object_id}')
    obj = Metafield.objects.set(
        instance, namespace=namespace, key=key,
        value=value, value_type=value_type,
    )
    return ToolResult(output={
        'id': str(obj.id),
        'full_key': obj.full_key,
        'value': obj.value,
        'value_type': obj.value_type,
    }, display=f'set {obj.full_key} on {model}#{object_id}')


@tool(
    name='metafields.delete',
    description=(
        'Delete a metafield. Pass `model`, `object_id`, `namespace` '
        '(default ""), and `key`. HARD-GATED — pass `confirmed=True`, '
        '`hard_gate_ack="YES"`, AND `echo` (user types the metafield key '
        'back to confirm).'
    ),
    scopes=['system.write'],
    schema={
        'type': 'object',
        'properties': {
            'model': {'type': 'string'},
            'object_id': {'type': 'string'},
            'namespace': {'type': 'string', 'default': ''},
            'key': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
            'hard_gate_ack': {'type': 'string', 'description': 'Must equal "YES".'},
            'echo': {'type': 'string', 'description': 'User-typed key for confirmation.'},
        },
        'required': ['model', 'object_id', 'key'],
    },
    requires_approval=True,
)
def metafields_delete_tool(*, model: str, object_id: str, key: str,
                           namespace: str = '', confirmed: bool = False,
                           hard_gate_ack: str = '', echo: str = '') -> ToolResult:
    _require_confirmed(confirmed)
    _require_hard_gate(hard_gate_ack=hard_gate_ack, target_name=key, echo=echo)
    from django.apps import apps
    try:
        from plugins.installed.metafields.models import Metafield
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'metafields plugin unavailable: {e}') from e
    try:
        app_label, model_name = model.split('.', 1)
        m = apps.get_model(app_label, model_name)
    except (ValueError, LookupError) as e:
        raise ToolError(f'unknown model: {model}') from e
    instance = m.objects.filter(pk=object_id).first()
    if instance is None:
        raise ToolError(f'{model} not found: {object_id}')
    n = Metafield.objects.delete_for(instance, namespace=namespace, key=key)
    return ToolResult(output={'deleted': n},
                      display=f'deleted {n} metafield(s) on {model}#{object_id}')


# ── CMS ────────────────────────────────────────────────────────────────


@tool(
    name='cms.publish_page',
    description=(
        'Publish a CMS page (sets state=published). Pass `id` or '
        '`slug`. Requires `confirmed=True`.'
    ),
    scopes=['content.write'],
    schema={
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'slug': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
        },
    },
    requires_approval=True,
)
def cms_publish_page_tool(*, id: str = '', slug: str = '',
                          confirmed: bool = False) -> ToolResult:
    _require_confirmed(confirmed)
    try:
        from django.utils import timezone
        from plugins.installed.cms.models import Page
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'cms plugin unavailable: {e}') from e
    p = None
    if id:
        p = Page.objects.filter(pk=id).first()
    if p is None and slug:
        p = Page.objects.filter(slug=slug).first()
    if p is None:
        raise ToolError('page not found — pass id or slug')
    prev = getattr(p, 'state', '')
    p.state = 'published'
    if hasattr(p, 'published_at') and not getattr(p, 'published_at', None):
        p.published_at = timezone.now()
        p.save(update_fields=['state', 'published_at', 'updated_at']
               if hasattr(p, 'updated_at') else ['state', 'published_at'])
    else:
        p.save(update_fields=['state', 'updated_at']
               if hasattr(p, 'updated_at') else ['state'])
    return ToolResult(output={
        'page_id': str(p.pk), 'slug': getattr(p, 'slug', ''),
        'previous_state': prev, 'new_state': 'published',
    }, display=f'published "{getattr(p, "title", p.pk)}"')


@tool(
    name='cms.unpublish_page',
    description=(
        'Unpublish a CMS page (sets state=draft). Pass `id` or `slug`. '
        'Requires `confirmed=True`.'
    ),
    scopes=['content.write'],
    schema={
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'slug': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
        },
    },
    requires_approval=True,
)
def cms_unpublish_page_tool(*, id: str = '', slug: str = '',
                            confirmed: bool = False) -> ToolResult:
    _require_confirmed(confirmed)
    try:
        from plugins.installed.cms.models import Page
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'cms plugin unavailable: {e}') from e
    p = None
    if id:
        p = Page.objects.filter(pk=id).first()
    if p is None and slug:
        p = Page.objects.filter(slug=slug).first()
    if p is None:
        raise ToolError('page not found — pass id or slug')
    prev = getattr(p, 'state', '')
    p.state = 'draft'
    p.save(update_fields=['state', 'updated_at']
           if hasattr(p, 'updated_at') else ['state'])
    return ToolResult(output={
        'page_id': str(p.pk), 'slug': getattr(p, 'slug', ''),
        'previous_state': prev, 'new_state': 'draft',
    }, display=f'unpublished "{getattr(p, "title", p.pk)}"')
