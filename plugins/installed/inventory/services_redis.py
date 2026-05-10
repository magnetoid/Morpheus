"""Redis-backed atomic stock reservation (opt-in flash-sale path).

The default ``inventory.services.reserve_for_order`` uses Postgres
``select_for_update`` — correct, but each reservation needs a row
lock + roundtrip. Under flash-sale concurrency (~hundreds of adds /
second to one variant) that path serialises and tail latencies spike.

This module offers a Redis-fronted alternative:

  * ``reserve_atomic(variant_id, qty)`` runs a small Lua script that
    decrements ``stock:{variant_id}`` only if remaining ≥ qty. Single
    atomic op; no distributed lock.
  * ``release(variant_id, qty)`` increments the counter back.
  * ``reconcile_stock()`` (periodic Celery task) compares Redis to
    Postgres and alerts on drift > 1% — Redis stays the *fast* truth,
    Postgres remains the *audit* truth.

Wire-up is opt-in: an order placement that wants the fast path calls
``reserve_atomic`` before the Postgres write. The default
``InventoryService.reserve_for_order`` stays the source of truth for
non-flash traffic and for stores without Redis.

Enable by setting ``INVENTORY_REDIS_FAST_PATH=True`` on a per-store
basis (PluginConfig['inventory']) once a real flash-sale is on the
calendar — not by default.
"""
from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.inventory.redis')


# Lua: DECRBY only if remaining ≥ qty. Atomic on Redis single-thread.
_RESERVE_SCRIPT = """
local cur = tonumber(redis.call('GET', KEYS[1]) or '0')
local want = tonumber(ARGV[1])
if cur < want then return -1 end
redis.call('DECRBY', KEYS[1], want)
return cur - want
"""


def _conn():
    """Get a Redis client. Returns None when Redis is unconfigured."""
    try:
        from django.core.cache import cache
        return cache.client.get_client(write=True)
    except Exception as e:  # noqa: BLE001
        logger.debug('inventory.redis: cache client unavailable: %s', e)
        return None


def _key(variant_id: str) -> str:
    return f'stock:{variant_id}'


def prime_from_postgres(variant_id: str) -> int | None:
    """Copy the current available_quantity from Postgres into Redis.

    Called once per (variant, warehouse) pair to seed the counter
    before flash traffic. Returns the seeded value, or None on error.
    """
    r = _conn()
    if r is None:
        return None
    try:
        from django.db.models import F, Sum
        from plugins.installed.inventory.models import StockLevel
        total = StockLevel.objects.filter(variant_id=variant_id).aggregate(
            avail=Sum(F('quantity') - F('reserved_quantity'))
        )['avail'] or 0
        r.set(_key(variant_id), int(total))
        return int(total)
    except Exception as e:  # noqa: BLE001
        logger.warning('inventory.redis: prime failed for %s: %s', variant_id, e)
        return None


def reserve_atomic(variant_id: str, qty: int) -> bool:
    """Atomically decrement ``stock:{variant_id}`` if remaining ≥ qty.

    Returns True on success (counter decremented), False on
    insufficient stock OR Redis unavailable (caller should fall back
    to the Postgres path).
    """
    if qty <= 0:
        return True
    r = _conn()
    if r is None:
        return False
    try:
        remaining = r.eval(_RESERVE_SCRIPT, 1, _key(variant_id), qty)
    except Exception as e:  # noqa: BLE001
        logger.warning('inventory.redis: reserve_atomic failed: %s', e)
        return False
    return int(remaining) >= 0


def release(variant_id: str, qty: int) -> None:
    """Inverse of reserve_atomic — used on cancel / payment failure."""
    if qty <= 0:
        return
    r = _conn()
    if r is None:
        return
    try:
        r.incrby(_key(variant_id), qty)
    except Exception as e:  # noqa: BLE001
        logger.warning('inventory.redis: release failed: %s', e)


def reconcile_stock(*, drift_threshold_pct: float = 1.0) -> dict:
    """Compare Redis counters to Postgres source of truth.

    Returns ``{'checked': N, 'in_sync': N, 'drift': [(variant_id,
    redis, postgres, pct_drift), ...]}``. Logs a warning per drift over
    threshold. Called by the periodic task (see tasks.py).
    """
    r = _conn()
    if r is None:
        return {'checked': 0, 'in_sync': 0, 'drift': []}
    out: dict = {'checked': 0, 'in_sync': 0, 'drift': []}
    try:
        from django.db.models import F, Sum
        from plugins.installed.inventory.models import StockLevel
        keys = r.scan_iter('stock:*')
        for key in keys:
            try:
                key_s = key.decode() if isinstance(key, bytes) else key
                variant_id = key_s.split('stock:', 1)[1]
                redis_val = int(r.get(key) or 0)
                pg_val = StockLevel.objects.filter(variant_id=variant_id).aggregate(
                    avail=Sum(F('quantity') - F('reserved_quantity'))
                )['avail'] or 0
                out['checked'] += 1
                if redis_val == int(pg_val):
                    out['in_sync'] += 1
                    continue
                denom = max(int(pg_val), 1)
                pct = abs(redis_val - int(pg_val)) / denom * 100.0
                if pct > drift_threshold_pct:
                    out['drift'].append((variant_id, redis_val, int(pg_val), pct))
                    logger.warning(
                        'inventory.redis: drift on %s — redis=%s postgres=%s (%.1f%%)',
                        variant_id, redis_val, pg_val, pct,
                    )
            except Exception as e:  # noqa: BLE001
                logger.debug('inventory.redis: drift check skipped key %r: %s', key, e)
                continue
    except Exception as e:  # noqa: BLE001
        logger.warning('inventory.redis: reconcile failed: %s', e)
    return out
