"""Cart-add stock reservations with Redis TTL.

The DB-side reservation pipeline (``InventoryService.reserve_for_order``)
runs at checkout — by then, two customers can already have raced to add
the last unit to their carts. This module closes that window by holding
a short-lived reservation in Redis from cart-add to either checkout or
TTL expiry (default 15 minutes).

Why Redis, not the DB:
  - Cart adds are 10-100× more frequent than checkouts; DB-side reserve
    bumps per add would write-storm the StockLevel table.
  - The TTL semantics are perfect — abandoned carts release their hold
    automatically without a sweeper task.
  - Cluster-friendly — atomic INCRBY/DECRBY is built in.

Failure model:
  - Redis unavailable → reservations no-op (return ok=True). We don't
    block carts on cache-layer outages; the DB reservation at checkout
    still enforces actual stock. Cart-time reservation is a CRO feature
    (don't show "in stock" if someone else has it), not a correctness
    feature.
  - Reservation races between two cart-add requests are resolved by
    Redis Lua script (CHECK-AND-INCR atomic).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import caches
from django_redis import get_redis_connection

logger = logging.getLogger('morpheus.inventory.cart_reservations')

# Reservation TTL — the window between cart-add and either checkout or
# expiry. 15 minutes is the e-commerce convention (Shopify, BigCommerce).
# Configurable per shop via SELF_IMPROVEMENT.cart_reservation_ttl_seconds
# or fallback to the more readable settings.CART_RESERVATION_TTL_SECONDS.
DEFAULT_TTL_SECONDS = 15 * 60

# Redis key shape. The variant id is the partitioning column; cart id
# is the holder. Both go into the key so:
#   - INCR is atomic per (variant, cart).
#   - We can SUM all carts' holds for one variant cheaply with
#     SCAN MATCH cart_reserve:<variant>:*.
KEY_PREFIX = 'cart_reserve'


@dataclass(slots=True)
class ReservationResult:
    """Return shape for `reserve()` — `ok=False` blocks the cart-add."""

    ok: bool
    held: int  # the quantity now held for this cart (post-reserve)
    available: int  # remaining reservable across all carts
    reason: str = ''


def reserve(*, variant_id: str, cart_id: str, quantity: int) -> ReservationResult:
    """Atomically increase this cart's hold on the variant.

    Returns ok=True if the new total fits within the variant's available
    stock minus all other carts' active holds. Otherwise ok=False and
    the caller should refuse the cart-add.
    """
    if quantity <= 0:
        return ReservationResult(
            ok=True, held=0, available=_available(variant_id), reason='zero qty'
        )

    if not _reservations_enabled():
        return ReservationResult(ok=True, held=quantity, available=0, reason='disabled')

    ttl = _ttl_seconds()
    try:
        # The Lua script below is the atomic CHECK-AND-INCR. It runs
        # entirely inside Redis so concurrent cart-adds can't race past
        # each other.
        conn = _redis()
        if conn is None:
            return ReservationResult(ok=True, held=quantity, available=0, reason='no_redis')

        new_total = conn.eval(
            _LUA_RESERVE,
            1,  # number of KEYS
            _self_key(variant_id, cart_id),
            quantity,
            ttl,
            _scan_pattern(variant_id),
            _absolute_available(variant_id),
        )

        if new_total == -1:
            # Lua returns -1 when the reservation would exceed stock.
            return ReservationResult(
                ok=False,
                held=_current_held(variant_id, cart_id),
                available=max(0, _available(variant_id)),
                reason='insufficient_stock',
            )
        return ReservationResult(
            ok=True,
            held=int(new_total),
            available=max(0, _available(variant_id)),
        )
    except Exception:  # noqa: BLE001 — never block cart adds on Redis errors
        logger.exception(
            'cart_reservations: reserve() failed for variant=%s cart=%s; treating as ok',
            variant_id,
            cart_id,
        )
        return ReservationResult(ok=True, held=quantity, available=0, reason='error')


def release(*, variant_id: str, cart_id: str, quantity: int | None = None) -> None:
    """Release some or all of this cart's hold on the variant.

    `quantity=None` releases the entire hold (cart-item delete). Called
    from CartService.remove_item and from the order-confirmation flow
    (DB-side reserve_for_order takes over from there).
    """
    if not _reservations_enabled():
        return
    try:
        conn = _redis()
        if conn is None:
            return
        key = _self_key(variant_id, cart_id)
        if quantity is None:
            conn.delete(key)
        else:
            current = int(conn.get(key) or 0)
            new = max(0, current - max(0, int(quantity)))
            if new == 0:
                conn.delete(key)
            else:
                conn.set(key, new, ex=_ttl_seconds(), keepttl=False)
    except Exception:  # noqa: BLE001 — release is best-effort
        logger.exception(
            'cart_reservations: release() failed for variant=%s cart=%s',
            variant_id,
            cart_id,
        )


def release_cart(cart_id: str) -> int:
    """Release every variant this cart has reserved.

    Called from checkout-success (DB reservation takes over) and from
    explicit cart-clear actions. Returns count released.
    """
    if not _reservations_enabled():
        return 0
    try:
        conn = _redis()
        if conn is None:
            return 0
        cursor = 0
        released = 0
        # Cart id appears as the last segment in every key shape; scan
        # for `cart_reserve:*:<cart_id>` so we hit just this cart.
        pattern = f'{KEY_PREFIX}:*:{cart_id}'
        while True:
            cursor, keys = conn.scan(cursor=cursor, match=pattern, count=200)
            if keys:
                conn.delete(*keys)
                released += len(keys)
            if cursor == 0:
                break
        return released
    except Exception:  # noqa: BLE001
        logger.exception('cart_reservations: release_cart failed for cart=%s', cart_id)
        return 0


def total_held(variant_id: str) -> int:
    """Sum of active cart holds for one variant — used by services that
    want to show 'X left' on the PDP without counting other shoppers'
    in-flight carts as inventory."""
    if not _reservations_enabled():
        return 0
    try:
        conn = _redis()
        if conn is None:
            return 0
        cursor = 0
        running = 0
        while True:
            cursor, keys = conn.scan(cursor=cursor, match=_scan_pattern(variant_id), count=200)
            for key in keys:
                val = conn.get(key)
                if val is None:
                    continue
                try:
                    running += int(val)
                except (TypeError, ValueError):
                    continue
            if cursor == 0:
                break
        return running
    except Exception:  # noqa: BLE001
        logger.exception('cart_reservations: total_held failed for variant=%s', variant_id)
        return 0


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

# Lua script for atomic CHECK-AND-INCR.
#
# KEYS[1] = self key (cart_reserve:variant:cart)
# ARGV[1] = quantity to add (signed int as string)
# ARGV[2] = TTL seconds
# ARGV[3] = scan pattern for SUM (cart_reserve:variant:*)
# ARGV[4] = absolute available (StockLevel sum - existing DB reservations)
#
# Returns:
#   -1 if the new total would exceed (absolute_available)
#   the new total held by this cart otherwise.
_LUA_RESERVE = """
local self_key = KEYS[1]
local qty = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local pattern = ARGV[3]
local absolute = tonumber(ARGV[4])

local self_current = tonumber(redis.call('GET', self_key) or '0')
local others_total = 0
local cursor = '0'
repeat
  local res = redis.call('SCAN', cursor, 'MATCH', pattern, 'COUNT', 200)
  cursor = res[1]
  for _, k in ipairs(res[2]) do
    if k ~= self_key then
      others_total = others_total + tonumber(redis.call('GET', k) or '0')
    end
  end
until cursor == '0'

local proposed = self_current + qty
if (proposed + others_total) > absolute then
  return -1
end

redis.call('SET', self_key, proposed, 'EX', ttl)
return proposed
"""


def _redis():
    """Return a redis-py connection or None if unavailable."""
    try:
        return get_redis_connection('default')
    except Exception:  # noqa: BLE001 — Redis may not be configured in dev
        return None


def _reservations_enabled() -> bool:
    cfg = getattr(settings, 'CART_RESERVATIONS', None)
    if cfg is None:
        # default on in production, off in tests
        return not getattr(settings, 'TESTING', False)
    return bool(cfg.get('enabled', True))


def _ttl_seconds() -> int:
    cfg = getattr(settings, 'CART_RESERVATIONS', {}) or {}
    return int(cfg.get('ttl_seconds') or DEFAULT_TTL_SECONDS)


def _self_key(variant_id: str, cart_id: str) -> str:
    return f'{KEY_PREFIX}:{variant_id}:{cart_id}'


def _scan_pattern(variant_id: str) -> str:
    return f'{KEY_PREFIX}:{variant_id}:*'


def _current_held(variant_id: str, cart_id: str) -> int:
    try:
        conn = _redis()
        if conn is None:
            return 0
        val = conn.get(_self_key(variant_id, cart_id))
        return int(val) if val else 0
    except Exception:  # noqa: BLE001
        return 0


def _absolute_available(variant_id: str) -> int:
    """StockLevel.available_quantity sum minus existing DB reservations.

    This is the "absolute" cap that cart reservations + DB reservations
    must together not exceed.
    """
    # Lazy import — keep this module light.
    from plugins.installed.inventory.models import StockLevel  # noqa: PLC0415

    try:
        return sum(sl.available_quantity for sl in StockLevel.objects.filter(variant_id=variant_id))
    except Exception:  # noqa: BLE001
        logger.exception('cart_reservations: _absolute_available query failed')
        return 0


def _available(variant_id: str) -> int:
    """Reservable units remaining: absolute - sum(cart_holds across all carts)."""
    absolute = _absolute_available(variant_id)
    held = total_held(variant_id)
    return max(0, absolute - held)


# Light proxy to confirm the default cache is reachable when called
# from a healthcheck. Re-exports a noop binding so callers don't have
# to import caches directly.
def cache_alive() -> bool:
    try:
        caches['default'].set('cart_reserve:_alive', '1', timeout=1)
        return caches['default'].get('cart_reserve:_alive') == '1'
    except Exception:  # noqa: BLE001
        return False
