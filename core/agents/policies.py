"""
Agent policies — capability/scope/budget guards.

Every agent declares the scopes it requires. Every tool declares the
scopes a caller must hold. The runtime intersects them before invocation
so an under-scoped agent never even sees an over-scoped tool.
"""

from __future__ import annotations

from decimal import Decimal


class AgentPolicyError(RuntimeError):
    """Raised when an agent action violates platform policy."""


class ScopeDenied(AgentPolicyError):
    """Raised when the caller lacks one or more required scopes."""


class BudgetExceeded(AgentPolicyError):
    """Raised when an agent's run would exceed its budget cap."""


def enforce_policy(
    *,
    scopes: list[str],
    required: list[str],
) -> None:
    """Assert that `scopes` satisfies all entries in `required`."""
    missing = [r for r in required if r not in scopes]
    if missing:
        raise ScopeDenied(f'Missing required scopes: {sorted(missing)}')


def enforce_budget(
    *,
    spent: Decimal | float | int,
    cap: Decimal | float | int | None,
) -> None:
    if cap is None:
        return
    try:
        if Decimal(str(spent)) > Decimal(str(cap)):
            raise BudgetExceeded(f'Spend {spent} exceeded cap {cap}')
    except (ArithmeticError, ValueError) as e:
        raise BudgetExceeded(f'Invalid budget values: {e}') from e
