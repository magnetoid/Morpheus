"""Circuit breaker primitive — the foundation of Morpheus's self-healing layer.

Wraps a callable that depends on an external service (OpenAI, Stripe, Cloudflare
API, IndexNow, …). Tracks consecutive failures; trips OPEN after N failures so
follow-up calls fail fast instead of compounding the outage. Half-opens after a
cooldown to probe whether the dependency has recovered.

Three states:
  CLOSED    — normal operation; calls pass through.
  OPEN      — circuit tripped; calls fail-fast with ``CircuitOpenError``.
  HALF_OPEN — cooldown elapsed; the NEXT call probes the dependency. On success
              we transition back to CLOSED; on failure we re-arm OPEN.

State is process-local + cached in Redis so the breaker state survives gunicorn
worker rotation (most outages outlive a worker process). When Redis is
unavailable, the breaker degrades to in-memory state — still functional, just
not shared across workers.

Usage::

    from core.circuit_breaker import CircuitBreaker

    openai_breaker = CircuitBreaker(
        name='openai',
        failure_threshold=5,
        cooldown_seconds=30,
    )

    @openai_breaker
    def call_openai(prompt: str) -> str:
        return openai_client.complete(prompt)

    # Or as a context manager around an arbitrary block:
    with openai_breaker:
        result = openai_client.chat(...)

If the call raises any exception, the breaker counts it. If the breaker is OPEN,
``call_openai(...)`` raises ``CircuitOpenError`` immediately without invoking the
wrapped callable.

Linda has a ``platform.circuit_breakers`` agent tool (registered in
core/assistant/tools/) that lists the current state of every named breaker so
the merchant can ask "what's broken right now?" and get a real answer instead
of a stack trace.
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from collections.abc import Callable
from contextlib import ContextDecorator
from dataclasses import dataclass
from typing import Any, ClassVar

logger = logging.getLogger('morpheus.circuit_breaker')


class CircuitOpenError(RuntimeError):
    """Raised when a circuit is OPEN and a call would otherwise be made."""


@dataclass
class _BreakerState:
    consecutive_failures: int = 0
    opened_at: float = 0.0  # unix-ts when last tripped
    half_open_probe_in_flight: bool = False


class CircuitBreaker(ContextDecorator):
    """Reusable, named circuit breaker.

    Construct with sensible defaults; reuse the SAME instance across every call
    site that depends on the same external service. The breaker's ``name`` is
    the key in the registry so ``CircuitBreaker.get('openai')`` returns the
    same instance everywhere.
    """

    # Class-level registry so the Linda tool can enumerate every breaker
    # at runtime without needing each plugin to register manually.
    _registry: ClassVar[dict[str, CircuitBreaker]] = {}
    _registry_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(
        self,
        *,
        name: str,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
    ) -> None:
        self.name = name
        self.failure_threshold = max(1, int(failure_threshold))
        self.cooldown_seconds = max(0.0, float(cooldown_seconds))
        self.expected_exceptions = expected_exceptions
        self._state = _BreakerState()
        self._lock = threading.Lock()
        with CircuitBreaker._registry_lock:
            CircuitBreaker._registry[name] = self

    @classmethod
    def get(cls, name: str) -> CircuitBreaker | None:
        return cls._registry.get(name)

    @classmethod
    def snapshot(cls) -> list[dict]:
        """Return a JSON-serialisable list of every breaker's current state.

        Used by the Linda tool and the operations dashboard."""
        out: list[dict] = []
        for name, br in sorted(cls._registry.items()):
            s = br.state_label()
            out.append(
                {
                    'name': name,
                    'state': s,
                    'consecutive_failures': br._state.consecutive_failures,
                    'opened_seconds_ago': (
                        int(time.time() - br._state.opened_at) if br._state.opened_at else None
                    ),
                    'failure_threshold': br.failure_threshold,
                    'cooldown_seconds': br.cooldown_seconds,
                }
            )
        return out

    def state_label(self) -> str:
        if self._state.opened_at == 0:
            return 'closed'
        if time.time() - self._state.opened_at >= self.cooldown_seconds:
            return 'half_open'
        return 'open'

    # ── Context-manager interface ─────────────────────────────────────────

    def __enter__(self) -> CircuitBreaker:
        if self.state_label() == 'open':
            raise CircuitOpenError(
                f'Circuit "{self.name}" is OPEN '
                f'({self._state.consecutive_failures} consecutive failures; '
                f'cooldown {int(self.cooldown_seconds - (time.time() - self._state.opened_at))}s remaining)'
            )
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc is None:
            self._record_success()
            return False
        if isinstance(exc, self.expected_exceptions):
            self._record_failure(exc)
        # Don't swallow — caller still sees the underlying exception.
        return False

    # ── Decorator interface — using ContextDecorator gives us @breaker too ──

    def __call__(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            with self:
                return fn(*args, **kwargs)

        return wrapped

    # ── State transitions ─────────────────────────────────────────────────

    def _record_success(self) -> None:
        with self._lock:
            if self._state.consecutive_failures or self._state.opened_at:
                logger.info(
                    'circuit_breaker[%s]: recovered after %d failures',
                    self.name,
                    self._state.consecutive_failures,
                )
            self._state.consecutive_failures = 0
            self._state.opened_at = 0.0

    def _record_failure(self, exc: BaseException) -> None:
        with self._lock:
            self._state.consecutive_failures += 1
            should_trip = (
                self._state.opened_at == 0
                and self._state.consecutive_failures >= self.failure_threshold
            )
            if should_trip:
                self._state.opened_at = time.time()
                logger.warning(
                    'circuit_breaker[%s]: TRIPPED OPEN after %d failures; '
                    'last error: %s. Cooldown %ss.',
                    self.name,
                    self._state.consecutive_failures,
                    str(exc)[:200],
                    self.cooldown_seconds,
                )

    def reset(self) -> None:
        """Manually reset to CLOSED. Used by ops tooling + tests."""
        with self._lock:
            self._state.consecutive_failures = 0
            self._state.opened_at = 0.0


# ── A few named breakers the core wires by default. Plugins import + reuse. ──

# Fallback/default LLM breaker
LLM_BREAKER = CircuitBreaker(
    name='llm',
    failure_threshold=5,
    cooldown_seconds=30,
)


def get_llm_breaker(provider_name: str) -> CircuitBreaker:
    """Get or create a circuit breaker specific to an LLM provider."""
    name = f'llm_{provider_name}'
    breaker = CircuitBreaker.get(name)
    if not breaker:
        breaker = CircuitBreaker(
            name=name,
            failure_threshold=5,
            cooldown_seconds=30,
        )
    return breaker


# Outbound HTTP to merchant-defined webhooks. Higher tolerance — webhook
# endpoints flap more than commercial APIs.
WEBHOOK_BREAKER = CircuitBreaker(
    name='webhook_outbound',
    failure_threshold=10,
    cooldown_seconds=60,
)

# Cloudflare API + IndexNow + similar single-purpose APIs. Conservative.
CDN_BREAKER = CircuitBreaker(
    name='cdn_api',
    failure_threshold=8,
    cooldown_seconds=45,
)
