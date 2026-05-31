"""Signal collectors — one per source.

Each collector either:
  - Runs on a Celery Beat schedule (error_log, seo_gap, code_quality,
    upstream_drift, dep_scan, lighthouse, dead_link).
  - Subscribes to a hooks-bus event (zero_search, cart_abandon, csp).

All emit signals via `core.self_improvement.services.emit_signal()` so
dedup + suppression behave the same way everywhere.

Pluggability: feature plugins can register additional collectors via
the `self_improvement.register_collector` hook (wired in apps.py).
"""

from core.self_improvement.collectors.base import Collector, Signal

__all__ = ['Collector', 'Signal']
