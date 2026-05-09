"""Workflow execution engine.

Hooks into `core.hooks.hook_registry` for every supported trigger
event. When the hook fires, the engine pulls every active Workflow
matching that trigger, evaluates each one's `condition` against the
event payload, and runs the actions for the ones that match. Each
execution writes a `WorkflowRun` row for audit.

Conditions are a tiny safe AST — no eval, no template language, just
recursive dict walking. Operators:

  {"all": [c1, c2, ...]}      → all sub-conditions true
  {"any": [c1, c2, ...]}      → at least one true
  {"not": c1}                 → negate
  {"==": ["path", value]}     → equality
  {"!=": ["path", value]}
  {">":  ["path", value]}
  {"<":  ["path", value]}
  {">=": ["path", value]}
  {"<=": ["path", value]}
  {"in": ["needle", "haystack"]}  → string substring or list contains
  {"contains": ["path", needle]}  → path resolves to a string/list
                                    that contains `needle`

`path` is a dotted lookup over the event payload (e.g. `order.total`,
`return_request.reason`). Missing paths resolve to None.

Actions live in ACTION_HANDLERS. Each handler takes `(spec, payload)`
and returns `(ok, message)`. Spec is the dict from
`Workflow.actions[i]`; payload is the merged event kwargs + the
resolved domain object.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

from django.utils import timezone

logger = logging.getLogger('morpheus.workflows.engine')


# ── Trigger registration ────────────────────────────────────────────────
# Plugin.ready() calls register_hook_listeners(self) which subscribes
# the engine to every trigger event in TRIGGER_CHOICES via the plugin's
# self.register_hook(...). One subscription per event, fanned out by
# `_dispatch` to the Workflow rows that match.

def register_hook_listeners(plugin) -> None:
    from plugins.installed.workflows.models import TRIGGER_CHOICES
    for event_name, _label in TRIGGER_CHOICES:
        plugin.register_hook(event_name, _make_listener(event_name), priority=70)


def _make_listener(event_name: str):
    def _listener(**kwargs):
        try:
            _dispatch(event_name, kwargs)
        except Exception as e:  # noqa: BLE001 — never let a workflow break the upstream
            logger.warning('workflow dispatch on %s failed: %s', event_name, e, exc_info=True)
    return _listener


def _dispatch(event_name: str, payload: dict) -> None:
    from plugins.installed.workflows.models import Workflow
    workflows = list(Workflow.objects.filter(trigger=event_name, is_active=True))
    if not workflows:
        return
    for wf in workflows:
        run_workflow(wf, payload)


# ── Public API ──────────────────────────────────────────────────────────


def run_workflow(workflow, payload: dict, *, dry_run: bool = False):
    """Evaluate condition + execute actions. Persists a WorkflowRun row.

    `dry_run=True` evaluates the condition + checks action validity
    without firing handlers. Used by the dashboard's "Test" button so
    merchants can verify a workflow against a sample payload safely.
    """
    from plugins.installed.workflows.models import WorkflowRun
    started = time.monotonic()
    snapshot = _serialize_payload(payload)

    matched = True
    if workflow.condition:
        try:
            matched = _eval(workflow.condition, payload)
        except Exception as e:  # noqa: BLE001
            return WorkflowRun.objects.create(
                workflow=workflow, state='failed',
                payload=snapshot, error=f'condition error: {e}',
                duration_ms=int((time.monotonic() - started) * 1000),
            )

    if not matched:
        run = WorkflowRun.objects.create(
            workflow=workflow, state='skipped',
            payload=snapshot,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return run

    actions_taken = []
    overall_error = ''
    for spec in (workflow.actions or []):
        kind = (spec.get('kind') or '').strip()
        handler = ACTION_HANDLERS.get(kind)
        if handler is None:
            actions_taken.append({'kind': kind, 'ok': False, 'message': f'unknown action kind: {kind}'})
            continue
        if dry_run:
            actions_taken.append({'kind': kind, 'ok': True, 'message': '(dry run — not executed)'})
            continue
        try:
            ok, message = handler(spec, payload)
            actions_taken.append({'kind': kind, 'ok': ok, 'message': message})
        except Exception as e:  # noqa: BLE001
            actions_taken.append({'kind': kind, 'ok': False, 'message': f'{type(e).__name__}: {e}'})
            overall_error = (overall_error or '') + f'\n[{kind}] {e}'

    run = WorkflowRun.objects.create(
        workflow=workflow,
        state='failed' if overall_error else 'matched',
        payload=snapshot,
        actions_taken=actions_taken,
        error=overall_error.strip(),
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    if not dry_run:
        workflow.run_count = (workflow.run_count or 0) + 1
        workflow.last_ran_at = timezone.now()
        workflow.last_error = (overall_error or '').strip()[:5000]
        workflow.save(update_fields=['run_count', 'last_ran_at', 'last_error', 'updated_at'])
    return run


# ── Condition AST evaluator ─────────────────────────────────────────────


def _resolve_path(payload: Any, path: str):
    """Dotted lookup over dicts + objects. Missing → None."""
    cur = payload
    for part in (path or '').split('.'):
        if cur is None or not part:
            return cur
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur


def _resolve(value: Any, payload: Any):
    """If `value` is a string, treat it as a dotted path. Otherwise return as-is.

    Lets condition specs use literals AND payload references in the
    same operand list:
      {"==": ["order.payment_status", "paid"]}
      {">":  ["order.total.amount", 100]}
    """
    if isinstance(value, str):
        # Heuristic: dotted strings resolve as paths; bare strings stay literals.
        # Operands rarely want literal strings WITHOUT dots so this is safe.
        if '.' in value:
            return _resolve_path(payload, value)
    return value


def _eval(node: Any, payload: Any) -> bool:
    """Recursive condition evaluator. Returns False on malformed input."""
    if not isinstance(node, dict) or not node:
        return True  # empty / non-dict → match-all
    if 'all' in node:
        return all(_eval(c, payload) for c in node['all'])
    if 'any' in node:
        return any(_eval(c, payload) for c in node['any'])
    if 'not' in node:
        return not _eval(node['not'], payload)
    for op in ('==', '!=', '>', '<', '>=', '<='):
        if op in node:
            args = node[op]
            if not isinstance(args, list) or len(args) != 2:
                return False
            left = _resolve(args[0], payload)
            right = _resolve(args[1], payload)
            try:
                if op == '==':
                    return left == right
                if op == '!=':
                    return left != right
                if op == '>':
                    return left is not None and right is not None and left > right
                if op == '<':
                    return left is not None and right is not None and left < right
                if op == '>=':
                    return left is not None and right is not None and left >= right
                if op == '<=':
                    return left is not None and right is not None and left <= right
            except TypeError:
                return False
    if 'in' in node:
        args = node['in']
        if not isinstance(args, list) or len(args) != 2:
            return False
        needle = _resolve(args[0], payload)
        haystack = _resolve(args[1], payload)
        try:
            return needle in haystack
        except TypeError:
            return False
    if 'contains' in node:
        args = node['contains']
        if not isinstance(args, list) or len(args) != 2:
            return False
        haystack = _resolve(args[0], payload)
        needle = _resolve(args[1], payload)
        try:
            return needle in (haystack or '')
        except TypeError:
            return False
    return False


def _serialize_payload(payload: dict) -> dict:
    """Best-effort JSON-safe snapshot. Anything not serialisable becomes a stringified placeholder."""
    out = {}
    for k, v in (payload or {}).items():
        try:
            import json
            json.dumps({k: v}, default=str)
            out[k] = v
        except Exception:  # noqa: BLE001
            out[k] = f'<{type(v).__name__}>'
    return out


# ── Action handlers ─────────────────────────────────────────────────────


def _action_notify_staff(spec: dict, payload: dict) -> tuple[bool, str]:
    """spec: {kind: notify_staff, title, body?, action_url?, icon?, kind_tag?}"""
    try:
        from plugins.installed.notifications_center.services import notify_all_staff
    except Exception as e:  # noqa: BLE001
        return False, f'notifications plugin unavailable: {e}'
    title = (spec.get('title') or '').strip() or 'Workflow event'
    body = (spec.get('body') or '').strip()
    action_url = (spec.get('action_url') or '').strip()
    icon = (spec.get('icon') or 'bell').strip()
    kind_tag = (spec.get('kind_tag') or 'workflows.fired').strip()
    n = notify_all_staff(kind=kind_tag, title=title, body=body,
                         action_url=action_url, icon=icon)
    return True, f'notified {n} staff'


def _action_add_order_note(spec: dict, payload: dict) -> tuple[bool, str]:
    """spec: {kind: add_order_note, note}"""
    note = (spec.get('note') or '').strip()
    if not note:
        return False, 'no note text'
    order = payload.get('order') or _resolve_path(payload, 'order')
    if order is None:
        return False, 'no order in payload'
    try:
        existing = (getattr(order, 'notes', '') or '').strip()
        sep = '\n\n' if existing else ''
        order.notes = f'{existing}{sep}{note}'
        order.save(update_fields=['notes', 'updated_at']
                   if hasattr(order, 'updated_at') else ['notes'])
        return True, 'note appended'
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def _action_tag_customer(spec: dict, payload: dict) -> tuple[bool, str]:
    """spec: {kind: tag_customer, tag}.

    Stores the tag as a metafield (`workflows.tag` namespace) so this
    works for any user model that has metafields; we don't depend on
    a particular `tags` field shape.
    """
    tag = (spec.get('tag') or '').strip()
    if not tag:
        return False, 'no tag specified'
    customer = (payload.get('customer') or _resolve_path(payload, 'order.customer')
                or _resolve_path(payload, 'customer'))
    if customer is None or not getattr(customer, 'pk', None):
        return False, 'no customer in payload'
    try:
        from plugins.installed.metafields.models import Metafield
        # Append to existing list rather than overwrite.
        existing = Metafield.objects.for_obj(customer, ns='workflows')
        tags = existing.get('workflows.tags') or []
        if not isinstance(tags, list):
            tags = []
        if tag not in tags:
            tags.append(tag)
        Metafield.objects.set(customer, namespace='workflows', key='tags',
                              value=tags, value_type='json')
        return True, f'customer tagged "{tag}"'
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def _action_webhook_post(spec: dict, payload: dict) -> tuple[bool, str]:
    """spec: {kind: webhook_post, url, body?, headers?}"""
    url = (spec.get('url') or '').strip()
    if not url.startswith(('http://', 'https://')):
        return False, 'webhook url must be http(s)'
    try:
        import requests
    except ImportError:
        return False, '`requests` not installed'
    body = spec.get('body') or _serialize_payload(payload)
    headers = spec.get('headers') or {'Content-Type': 'application/json'}
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=10)
        return True, f'POST → {resp.status_code}'
    except Exception as e:  # noqa: BLE001
        return False, f'webhook error: {e}'


def _action_agent_skill(spec: dict, payload: dict) -> tuple[bool, str]:
    """spec: {kind: agent_skill, agent, message, context?}.

    Invokes a registered agent via `agent_core.services.run_agent`.
    The named agent must be in the `agent_registry`. Result is logged
    in the WorkflowRun.actions_taken record but doesn't gate anything
    upstream — workflow-driven agent calls are fire-and-forget.
    """
    agent_name = (spec.get('agent') or '').strip()
    message = (spec.get('message') or '').strip()
    if not (agent_name and message):
        return False, 'agent + message required'
    try:
        from plugins.installed.agent_core.services import run_agent
    except Exception as e:  # noqa: BLE001
        return False, f'agent_core unavailable: {e}'
    try:
        result = run_agent(
            agent_name=agent_name,
            user_message=message,
            customer=None,
            session_key='workflows-engine',
            context={**(spec.get('context') or {}), 'workflow_payload': _serialize_payload(payload)},
        )
        ok = (result.state == 'completed')
        return ok, f'{agent_name} → {result.state}'
    except Exception as e:  # noqa: BLE001
        return False, f'{type(e).__name__}: {e}'


ACTION_HANDLERS: dict[str, Callable[[dict, dict], tuple[bool, str]]] = {
    'notify_staff': _action_notify_staff,
    'add_order_note': _action_add_order_note,
    'tag_customer': _action_tag_customer,
    'webhook_post': _action_webhook_post,
    'agent_skill': _action_agent_skill,
}
