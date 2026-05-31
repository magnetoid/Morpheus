"""Collector base class + Signal data transfer object.

A `Collector` runs (on Beat or as a hook subscriber) and produces zero
or more `Signal` instances. The collector's `run()` is allowed to
either yield Signals (preferred — streaming, low memory) or return a
list.

The pluggable registry: feature plugins register a Collector subclass
via the `self_improvement.register_collector` hook (fired in
`core/self_improvement/apps.py:ready()`). The orchestrator picks them
up automatically — plugins never import from each other.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.self_improvement.services import emit_signal, finish_ingest_job, start_ingest_job


@dataclass(slots=True)
class Signal:
    """One raw observation, pre-persistence.

    Carries enough to dedup + score. The collector decides the
    fingerprint shape per source (see `services.fingerprint_for` for the
    canonical helper). `payload` is JSON-serialisable and stored as-is.
    """

    source: str
    fingerprint: str
    severity: int = 50
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime | None = None  # default: now() at write time


class Collector:
    """Subclass-and-implement contract.

    Subclasses set `name` (matches an SIGNAL_SOURCES key) and implement
    `run() -> Iterable[Signal]`. Drive it via `Collector.execute()` from
    a Celery task; that wraps the run in a SiIngestJob row so the
    dashboard can show collector health.
    """

    name: str = ''  # subclasses override; must match a SIGNAL_SOURCES key

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.name and cls.__name__ != 'Collector':
            raise TypeError(
                f'{cls.__name__} must set a `name` class attribute matching a SIGNAL_SOURCES key'
            )

    def run(self) -> Iterable[Signal]:
        """Yield signals. Subclasses must implement."""
        raise NotImplementedError

    def execute(self) -> int:
        """Run + persist, wrapped in an SiIngestJob.

        Returns the number of signals emitted (after dedup, suppression).
        On failure, the job is marked `failed` and the exception
        re-raised so the Celery task retries via its own policy.
        """
        job = start_ingest_job(self.name)
        emitted = 0
        try:
            for signal in self.run():
                row = emit_signal(
                    source=signal.source or self.name,
                    fingerprint=signal.fingerprint,
                    severity=signal.severity,
                    payload=signal.payload,
                    occurred_at=signal.occurred_at,
                )
                if row is not None:
                    emitted += 1
        except Exception as exc:  # noqa: BLE001 — failure path must record + re-raise
            finish_ingest_job(job, signals_emitted=emitted, status='failed', error=str(exc))
            raise
        finish_ingest_job(job, signals_emitted=emitted, status='ok')
        return emitted
