"""Observability services — the deprecated error-capture shim.

The metrics rollup that lived here (``core.OutboxEvent`` → ``MerchantMetric``)
was retired in v0.77.0; see ``plugins/installed/observability/models.py``.
"""

from __future__ import annotations


def record_error(
    *,
    source: str,
    message: str,
    stack_trace: str = '',
    channel=None,
    metadata: dict | None = None,
) -> None:
    """DEPRECATED shim — forwards to the core error system (ADR 0025).

    Error capture is a core system (`core/errors`); this string-based wrapper is
    kept only for back-compat so any lingering caller still lands in the unified,
    fingerprinted core table instead of the retired plugin ErrorEvent. New code
    should call `core.errors.services.record_error`/`record_message` directly.
    """
    from core.errors.services import record_message

    record_message(
        message,
        kind='server',
        source=source,
        stack_trace=stack_trace,
        extra=metadata or {},
    )
