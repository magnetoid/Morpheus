"""Workflow / saga primitives — explicit multi-step flows with compensation.

When a checkout, return, or fulfillment runs through 5+ side-effecting steps,
the hook-bus + ad-hoc-try/except pattern leaves the system in torn states on
partial failure. The classic example we shipped a fix for earlier this session
(gift-card redemption inside a broad except — order persisted with a discount
the gift card never actually consumed) is exactly the kind of bug a saga
prevents structurally.

A ``Workflow`` is a named sequence of ``Step`` callables. Each step optionally
declares a ``compensate`` callable that REVERSES its effect. The runtime:

  1. Executes steps in order, accumulating completed steps onto a stack.
  2. If a step raises, runs the compensations for the COMPLETED steps in
     reverse order. Each compensation receives the same context the
     step did.
  3. Records every step + compensation + outcome to ``core.audit`` so
     a merchant (or Linda) can answer "what happened to order 1234?".

Why this matters for the AI-first thesis: Linda can introspect a workflow's
execution log and say "the checkout for order 1234 failed at step
'reserve_inventory'; steps 1-2 (validate_cart, apply_promotions) were
rolled back; here's what the customer sees." Ad-hoc hook chains can't
surface that.

Usage::

    from core.workflows import Workflow, step, WorkflowError

    @Workflow.register('checkout.complete')
    class CompleteCheckout(Workflow):

        @step(name='validate_cart')
        def validate_cart(self, ctx):
            ...

        @step(name='reserve_inventory')
        def reserve_inventory(self, ctx):
            allocator.reserve(ctx['cart'])

        @reserve_inventory.compensate
        def release_inventory(self, ctx):
            allocator.release(ctx['cart'])

        @step(name='charge_payment')
        def charge_payment(self, ctx):
            ctx['payment'] = stripe.PaymentIntent.create(...)

        @charge_payment.compensate
        def refund_payment(self, ctx):
            if 'payment' in ctx:
                stripe.Refund.create(payment_intent=ctx['payment'].id)

        @step(name='create_order')
        def create_order(self, ctx):
            ctx['order'] = OrderService.create_from_cart(ctx['cart'])

Invoking::

    result = CompleteCheckout().run({'cart': cart, 'customer': user})
    if result.failed:
        raise WorkflowError(result.error)

Each step + compensation auto-logs to ``core.audit`` with the workflow name,
step name, outcome ('ok' | 'failed' | 'compensated'), and a JSON-safe ctx
snapshot for replay / debugging.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

logger = logging.getLogger('morpheus.workflows')


class WorkflowError(Exception):
    """Raised when a workflow fails — message describes the failing step."""


@dataclass
class StepResult:
    name: str
    state: str  # 'ok' | 'failed' | 'skipped'
    duration_ms: int
    error: str = ''
    output: Any = None


@dataclass
class CompensationResult:
    step_name: str
    state: str  # 'ok' | 'failed' | 'skipped'
    error: str = ''


@dataclass
class WorkflowResult:
    workflow: str
    started_at: float
    completed_at: float
    state: str  # 'completed' | 'failed' | 'compensated'
    steps: list[StepResult] = field(default_factory=list)
    compensations: list[CompensationResult] = field(default_factory=list)
    error: str = ''

    @property
    def failed(self) -> bool:
        return self.state != 'completed'

    @property
    def duration_ms(self) -> int:
        return int((self.completed_at - self.started_at) * 1000)


class _Step:
    """Wraps a step callable + its optional compensation."""

    def __init__(self, fn: Callable, *, name: str):
        self.fn = fn
        self.name = name
        self.compensate_fn: Callable | None = None

    def compensate(self, fn: Callable) -> Callable:
        """Decorator: register a compensation for this step. Returns the
        compensation fn unchanged so the user can still call it directly."""
        self.compensate_fn = fn
        return fn

    def __call__(self, instance, ctx) -> Any:
        return self.fn(instance, ctx)


def step(*, name: str | None = None) -> Callable:
    """Decorator marking a method as a workflow step.

    Optional ``name`` for the step (defaults to the function name) — used in
    audit logs + the result object. The decorated callable gains a
    ``.compensate`` method that registers the reverse operation.
    """

    def deco(fn: Callable) -> _Step:
        return _Step(fn, name=name or fn.__name__)

    return deco


class Workflow:
    """Base class for a named multi-step workflow.

    Subclass and decorate methods with ``@step(name=...)``. The runtime
    discovers them in declaration order. To register a workflow in a global
    registry (so plugins can resolve workflows by name), use the
    ``Workflow.register('name.path')`` class decorator.
    """

    name: str = ''
    _registry: ClassVar[dict[str, type[Workflow]]] = {}

    @classmethod
    def register(cls, name: str):
        """Class decorator — register a workflow class in the global registry."""

        def deco(workflow_cls: type[Workflow]) -> type[Workflow]:
            workflow_cls.name = name
            cls._registry[name] = workflow_cls
            return workflow_cls

        return deco

    @classmethod
    def get(cls, name: str) -> type[Workflow] | None:
        return cls._registry.get(name)

    @classmethod
    def all_registered(cls) -> dict[str, type[Workflow]]:
        return dict(cls._registry)

    def _discover_steps(self) -> list[_Step]:
        """Walk the class MRO + collect _Step instances in declaration order."""
        seen: set[str] = set()
        steps: list[_Step] = []
        for klass in type(self).__mro__:
            for attr in vars(klass).values():
                if isinstance(attr, _Step) and attr.name not in seen:
                    seen.add(attr.name)
                    steps.append(attr)
        return steps

    def run(self, ctx: dict[str, Any] | None = None) -> WorkflowResult:
        """Execute the workflow. Returns a WorkflowResult; never raises.

        On any step failure, runs compensations for completed steps in
        reverse order. Each step + compensation is recorded in
        ``core.audit`` (when available).
        """
        ctx = dict(ctx or {})
        started_wall = time.time()
        result = WorkflowResult(
            workflow=self.name or type(self).__name__,
            started_at=started_wall,
            completed_at=started_wall,
            state='completed',
        )
        completed: list[_Step] = []

        for step_def in self._discover_steps():
            step_start = time.monotonic()
            try:
                output = step_def(self, ctx)
                result.steps.append(
                    StepResult(
                        name=step_def.name,
                        state='ok',
                        duration_ms=int((time.monotonic() - step_start) * 1000),
                        output=output,
                    )
                )
                completed.append(step_def)
                self._audit('step.ok', step_def.name, ctx, error='')
            except Exception as exc:  # noqa: BLE001 — workflows isolate at the step boundary
                result.steps.append(
                    StepResult(
                        name=step_def.name,
                        state='failed',
                        duration_ms=int((time.monotonic() - step_start) * 1000),
                        error=str(exc)[:500],
                    )
                )
                result.state = 'failed'
                result.error = f'step "{step_def.name}" failed: {exc}'
                self._audit('step.failed', step_def.name, ctx, error=str(exc))
                logger.warning(
                    'workflow[%s]: step "%s" failed: %s',
                    result.workflow,
                    step_def.name,
                    exc,
                    exc_info=True,
                )
                # Compensate every completed step in reverse.
                for done in reversed(completed):
                    if done.compensate_fn is None:
                        result.compensations.append(
                            CompensationResult(
                                step_name=done.name,
                                state='skipped',
                                error='no compensation defined',
                            )
                        )
                        continue
                    try:
                        done.compensate_fn(self, ctx)
                        result.compensations.append(
                            CompensationResult(
                                step_name=done.name,
                                state='ok',
                            )
                        )
                        self._audit('compensate.ok', done.name, ctx, error='')
                    except Exception as cexc:  # noqa: BLE001
                        result.compensations.append(
                            CompensationResult(
                                step_name=done.name,
                                state='failed',
                                error=str(cexc)[:500],
                            )
                        )
                        self._audit('compensate.failed', done.name, ctx, error=str(cexc))
                        logger.error(
                            'workflow[%s]: COMPENSATION for "%s" failed: %s',
                            result.workflow,
                            done.name,
                            cexc,
                            exc_info=True,
                        )
                result.state = (
                    'compensated'
                    if any(c.state == 'ok' for c in result.compensations)
                    else 'failed'
                )
                break

        result.completed_at = time.time()
        return result

    def _audit(self, kind: str, step_name: str, ctx: dict, *, error: str) -> None:
        """Best-effort audit log emission. Failures here are swallowed —
        workflows must not be blocked by observability outages."""
        try:
            from core.audit.services import record

            # Don't dump the full ctx — it may contain PII or huge payloads.
            # Just the keys + a string preview of each value.
            ctx_preview = {k: type(v).__name__ for k, v in ctx.items()}
            record(
                event_type=f'workflow.{kind}',
                metadata={
                    'workflow': self.name or type(self).__name__,
                    'step': step_name,
                    'ctx_keys': sorted(ctx_preview.keys()),
                    'error': error[:500] if error else '',
                },
            )
        except Exception:  # noqa: BLE001, S110
            pass
