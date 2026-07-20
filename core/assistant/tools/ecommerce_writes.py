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

**Staged mode** (staged-changes design §2, docs/superpowers/specs/
2026-07-05-staged-changes-routines-design.md): when the run context carries
``{'staged': True}`` (set by routines; the runtime injects ``context`` into
any handler that declares it), a tool records an OpsProposal describing the
change it WOULD apply and returns "Staged proposal <id>: <title>" to the
LLM instead of executing. `core.safety` class-blocklist checks run at
staging time — a blocked kind (``pricing_change``) surfaces as a tool
error. Without the flag, behavior is unchanged.

Read tools live in `ecommerce.py` next door; nothing in this file
returns large result sets.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

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


def _is_staged(context) -> bool:
    """True when the run context asks for staged (propose-only) mode."""
    return bool(isinstance(context, dict) and context.get('staged'))


def _obj_ref(obj) -> str:
    """`'<app_label>.<model>:<pk>'` — the OpsProposal change-object format."""
    return f'{obj._meta.app_label}.{obj._meta.model_name}:{obj.pk}'


def _stage(
    *,
    context,
    tool_name: str,
    kind: str,
    title: str,
    summary: str,
    changes: list[dict],
    target=None,
) -> ToolResult:
    """Record an OpsProposal instead of executing (staged-changes design §2).

    A SafetyViolation (blocked kind) becomes a ToolError so the runtime
    returns the error text to the LLM rather than aborting the run.
    """
    from core.assistant.staging import stage_proposal
    from core.safety import SafetyViolation

    ctx = context if isinstance(context, dict) else {}
    try:
        proposal = stage_proposal(
            source=str(ctx.get('source') or f'skill:{tool_name}'),
            kind=kind,
            title=title,
            summary=summary,
            changes=changes,
            agent_run=ctx.get('agent_run'),
            target=target,
        )
    except SafetyViolation as e:
        raise ToolError(f'staging blocked by the safety boundary: {e}') from e
    text = f'Staged proposal {proposal.pk}: {proposal.title}'
    return ToolResult(output=text, display=text)


def _require_hard_gate(*, hard_gate_ack: str, target_name: str, echo: str) -> None:
    """Enforce the second-tier confirmation for destructive actions.

    The LLM must collect both:
      * ``hard_gate_ack="YES"`` — the magic acknowledgement string.
      * ``echo`` — the user's typed-back identifier (must match
        ``target_name`` case-insensitively).
    An ``agents.decision`` audit row is recorded (core.audit) for the trail.
    """
    if (hard_gate_ack or '').strip().upper() != 'YES':
        raise ToolError(_NEEDS_HARD_GATE)
    if (echo or '').strip().lower() != (target_name or '').strip().lower():
        raise ToolError(f'echo mismatch — user typed {echo!r} but the target is {target_name!r}.')
    # Record the hard-gate confirmation to the real audit sink. The previous
    # code called AgentApprovalRequest.objects.create(agent_name=…, payload=…)
    # with fields that don't exist on the model and a missing required `run` FK,
    # so it raised on EVERY destructive op and was swallowed — the audit row for
    # the platform's MOST destructive actions was never written (hunt #21).
    try:
        from core.audit.services import record_ai_decision

        record_ai_decision(
            agent='assistant',
            tool='hard_gate.confirm',
            target=target_name,
            args={'echo': echo, 'ack': 'YES'},
            output={'confirmed': True},
        )
    except Exception as exc:  # noqa: BLE001 — audit must never block the gate, but don't hide it
        import logging

        logging.getLogger('morpheus.assistant.ecommerce_writes').warning(
            'hard-gate audit record failed for %s: %s', target_name, exc, exc_info=True
        )


# ── Products ────────────────────────────────────────────────────────────


@tool(
    name='products.update_status',
    description=(
        "Set a product's status: active, draft, or archived. "
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
    supports_staging=True,
)
def products_update_status_tool(
    *,
    status: str,
    id: str = '',
    sku: str = '',
    slug: str = '',
    confirmed: bool = False,
    context: dict | None = None,
) -> ToolResult:
    staged = _is_staged(context)
    if not staged:
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
    if staged:
        return _stage(
            context=context,
            tool_name='products.update_status',
            kind='product.update',
            title=f'Product "{p.name}": {prev} → {status}',
            summary=f'Set product {p.name!r} (SKU {p.sku}) status from {prev!r} to {status!r}.',
            changes=[{'object': _obj_ref(p), 'field': 'status', 'old': prev, 'new': status}],
            target=p,
        )
    p.status = status
    p.save(update_fields=['status', 'updated_at'])
    return ToolResult(
        output={
            'product_id': str(p.id),
            'name': p.name,
            'previous_status': prev,
            'new_status': status,
        },
        display=f'{p.name}: {prev} → {status}',
    )


@tool(
    name='products.update_price',
    description=(
        "Update a product's price (optionally on a specific variant). "
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
    supports_staging=True,
)
def products_update_price_tool(
    *,
    price: str,
    id: str = '',
    sku: str = '',
    slug: str = '',
    variant_id: str = '',
    confirmed: bool = False,
    context: dict | None = None,
) -> ToolResult:
    staged = _is_staged(context)
    if not staged:
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
        if staged:
            # 'pricing_change' is in core.safety.CLASS_BLOCKLIST — staging
            # refuses it, deliberately: autonomous runs cannot propose price
            # edits (spec §2). The interactive confirmed flow still can.
            return _stage(
                context=context,
                tool_name='products.update_price',
                kind='pricing_change',
                title=f'Variant {v.sku}: {prev} → {amount}',
                summary=f'Change variant {v.sku} price from {prev} to {amount}.',
                changes=[
                    {'object': _obj_ref(v), 'field': 'price', 'old': prev, 'new': str(amount)}
                ],
                target=v,
            )
        # djmoney accepts a Decimal directly when assigned; the field's
        # currency is preserved from the existing value.
        v.price = amount
        v.save(update_fields=['price', 'updated_at'])
        return ToolResult(
            output={
                'variant_id': str(v.id),
                'sku': v.sku,
                'previous_price': prev,
                'new_price': str(amount),
            },
            display=f'variant {v.sku}: {prev} → {amount}',
        )

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
    if staged:
        # See the variant branch above — 'pricing_change' is blocklisted at
        # staging time (core.safety), so this surfaces as a tool error.
        return _stage(
            context=context,
            tool_name='products.update_price',
            kind='pricing_change',
            title=f'Product "{p.name}": {prev} → {amount}',
            summary=f'Change product {p.name!r} price from {prev} to {amount}.',
            changes=[{'object': _obj_ref(p), 'field': 'price', 'old': prev, 'new': str(amount)}],
            target=p,
        )
    p.price = amount
    p.save(update_fields=['price', 'updated_at'])
    return ToolResult(
        output={
            'product_id': str(p.id),
            'name': p.name,
            'previous_price': prev,
            'new_price': str(amount),
        },
        display=f'{p.name}: {prev} → {amount}',
    )


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
    supports_staging=True,
)
def customers_add_note_tool(
    *,
    note: str,
    id: str = '',
    email: str = '',
    confirmed: bool = False,
    context: dict | None = None,
) -> ToolResult:
    staged = _is_staged(context)
    if not staged:
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
    old_raw = getattr(u, 'notes', '') or ''
    existing = old_raw.strip()
    sep = '\n\n' if existing else ''
    if staged:
        return _stage(
            context=context,
            tool_name='customers.add_note',
            kind='customer.note',
            title=f'Add note to customer {u.email or u.pk}',
            summary=f'Append an internal note to customer {u.email or u.pk}.',
            changes=[
                {
                    'object': _obj_ref(u),
                    'field': 'notes',
                    'old': old_raw,
                    'new': f'{existing}{sep}{note.strip()}',
                }
            ],
            target=u,
        )
    u.notes = f'{existing}{sep}{note.strip()}'
    u.save(update_fields=['notes'])
    return ToolResult(
        output={'customer_id': str(u.pk), 'email': u.email, 'appended': True},
        display=f'note added to {u.email}',
    )
