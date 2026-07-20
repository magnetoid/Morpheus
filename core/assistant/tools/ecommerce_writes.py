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
