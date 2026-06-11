"""High-level Function services: dispatching, recording invocations."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from django.db import DatabaseError, transaction

logger = logging.getLogger('morpheus.functions')


def _serialize_value(value: Any) -> str:
    return str(getattr(value, 'amount', value))


def dispatch_filter(
    *,
    target: str,
    value: Any,
    input: Mapping[str, Any],
    channel: Any | None = None,
) -> Any:
    """
    Run all enabled functions for `target` and pipe `value` through them.
    Each function returns a new value (or `None` to leave it unchanged).
    """
    from plugins.installed.functions.models import Function
    from plugins.installed.functions.runtime import (
        FunctionError,
        FunctionExecutionError,
        execute,
    )

    try:
        qs = Function.objects.filter(target=target, is_enabled=True)
        if channel is not None:
            qs = qs.filter(channel=channel) | qs.filter(channel__isnull=True)
        functions = list(qs.order_by('priority', 'name'))
    except DatabaseError as e:
        logger.warning('functions: DB unavailable for target=%s: %s', target, e)
        return value

    if not functions:
        return value

    current = value
    payload = {**input, 'value': _serialize_value(current)}

    for fn in functions:
        try:
            result = execute(
                source=fn.source,
                input=payload,
                capabilities=list(fn.capabilities or []),
                timeout_ms=fn.timeout_ms,
            )
        except (FunctionError, FunctionExecutionError) as e:
            _record_invocation(fn, success=False, error=str(e), input=payload, output={})
            continue
        except Exception as e:  # noqa: BLE001 — runtime invariants only; never block hook chain
            _record_invocation(fn, success=False, error=str(e), input=payload, output={})
            logger.error('functions: unexpected error in %s: %s', fn.id, e, exc_info=True)
            continue

        out = result.output
        _record_invocation(
            fn,
            success=True,
            error='',
            input=payload,
            output={'value': out, 'duration_ms': result.duration_ms},
            duration_ms=result.duration_ms,
        )
        if out is None:
            continue
        current = _coerce_money(out, current)
        payload = {**payload, 'value': _serialize_value(current)}

    return current


def _coerce_money(out: Any, original: Any) -> Any:
    """If the original value was a Money, coerce a numeric result back into Money."""
    try:
        from djmoney.money import Money
    except ImportError:
        Money = None  # type: ignore[assignment]
    if Money is None or not isinstance(original, Money):
        return out
    if isinstance(out, Money):
        return out
    try:
        return Money(Decimal(str(out)), original.currency)
    except (ValueError, ArithmeticError):
        return original


def _record_invocation(
    fn,
    *,
    success: bool,
    error: str,
    input: Mapping[str, Any],
    output: Mapping[str, Any],
    duration_ms: int = 0,
) -> None:
    from plugins.installed.functions.models import Function, FunctionInvocation

    try:
        with transaction.atomic():
            FunctionInvocation.objects.create(
                function=fn,
                duration_ms=duration_ms,
                success=success,
                error_message=error[:1000],
                input_summary={
                    k: v
                    for k, v in input.items()
                    if k in ('value', 'product_id', 'cart_id', 'customer_id', 'subtotal')
                },
                output_summary={'value': output.get('value')} if output else {},
            )
            updates = {
                'invocation_count': fn.invocation_count + 1,
                'last_run_ms': duration_ms or fn.last_run_ms,
            }
            if not success:
                updates['error_count'] = fn.error_count + 1
                updates['last_error'] = error[:2000]
            else:
                updates['last_error'] = ''
            Function.objects.filter(pk=fn.pk).update(**updates)
    except DatabaseError as e:
        logger.warning('functions: failed to record invocation for %s: %s', fn.id, e)
