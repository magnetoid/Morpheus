"""
Per-merchant observability — the retired plugin error log.

The metrics rollup (`MerchantMetric`, fed from `core.OutboxEvent`) was removed
in v0.77.0: the outbox is only written when a NATS broker is configured, so on
every deployment without one the rollup had read nothing since 2026-07-12 and
its GraphQL series sat frozen at that date, unread by any dashboard surface.

`ErrorEvent` left in v0.122.0; `core.errors` keeps the log.
"""

from __future__ import annotations
