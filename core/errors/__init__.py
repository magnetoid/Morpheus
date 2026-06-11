"""Deep error logging — server-side 500 capture + client-side JS error capture.

Both feed the same `ErrorEvent` model and the dashboard at
``/dashboard/errors/``. Distinct from ``core.audit`` (security-relevant
"who did what") and ``core.observability`` (OpenTelemetry traces / metrics):

* **core.errors**       — exceptions, stack traces, "something broke".
* **core.audit**        — actions, decisions, "who did what when".
* **core.observability** — latency, throughput, "how the system is behaving".

Usage from code:

    from core.errors import record_error
    try:
        ...
    except Exception as e:  # noqa: BLE001
        record_error(e, request=request, kind='server')
        raise
"""

from __future__ import annotations

from core.errors.services import record_error

__all__ = ['record_error']
