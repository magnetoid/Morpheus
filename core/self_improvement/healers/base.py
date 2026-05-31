"""Healer ABC + dispatch registry.

A Healer is the executor for one issue class. It receives a
SiRecommendation and must implement:

  - propose() — return a dict describing what would change. Pure, no
    side effects. Called both at planning time and for the diff view.
  - safe_to_apply(recommendation) — final guard. Even if the policy
    matrix allows auto-apply, the healer can refuse (e.g. the row
    we'd update no longer exists).
  - apply() — actually make the change. Idempotent where possible.
    Returns a HealResult that the orchestrator writes to si_action_log.
  - verify() — confirm the change took (re-query, curl, etc.).
  - rollback() — best-effort revert. Optional.

Phase 2 healers all touch DATA only (Product fields, Redirect rows,
SearchSynonym rows). Code-touching healers ship in Phase 3.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger('morpheus.self_improvement.healers')


@dataclass(slots=True)
class HealResult:
    ok: bool
    details: dict = field(default_factory=dict)
    error: str = ''


class Healer(ABC):
    """Subclass per issue class. Set ``class_name``."""

    class_name: str = ''

    @abstractmethod
    def propose(self, recommendation) -> dict:
        """Return {kind, files, patch, ...} for the dashboard preview."""

    @abstractmethod
    def safe_to_apply(self, recommendation) -> tuple[bool, str]:
        """(ok, reason). Final guard."""

    @abstractmethod
    def apply(self, recommendation) -> HealResult:
        """Make the change. Must be idempotent or guarded."""

    def verify(self, recommendation) -> HealResult:  # noqa: ARG002
        """Default: assume apply() returned True == verified."""
        return HealResult(ok=True)

    def rollback(self, recommendation) -> HealResult:  # noqa: ARG002
        """Best-effort revert. Default is no-op."""
        return HealResult(ok=True)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[Healer]] = {}


def register_healer(class_name: str) -> Any:
    """Decorator. Use as ``@register_healer('seo_gap')`` on the
    Healer subclass."""

    def _decorate(cls):
        if not issubclass(cls, Healer):
            raise TypeError(f'{cls.__name__} must subclass Healer')
        cls.class_name = class_name
        _REGISTRY[class_name] = cls
        return cls

    return _decorate


def get_healer(class_name: str) -> Healer | None:
    cls = _REGISTRY.get(class_name)
    return cls() if cls else None


def known_classes() -> list[str]:
    return sorted(_REGISTRY)
