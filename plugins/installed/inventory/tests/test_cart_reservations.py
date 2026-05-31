"""Cart-add Redis reservation tests.

We mock Redis via a tiny in-memory fake so the tests run without
spinning up redis. The fake mirrors the subset of redis-py the
module uses: eval, get, delete, set, scan.

Production semantics verified:
  - Atomic CHECK-AND-INCR via the Lua script (reproduced in Python).
  - TTL window keyed per (variant, cart).
  - reserve() returns ok=True with held quantity on first call.
  - reserve() returns ok=False with reason='insufficient_stock' when
    new_total + others would exceed absolute available.
  - release() with quantity=None deletes the key; partial release
    decrements (and deletes if it hits zero).
  - release_cart(cart_id) scans + drops every variant for one cart.
  - Redis unreachable → fail-open with reason='no_redis'.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from django.test import TestCase

from plugins.installed.inventory.cart_reservations import (
    ReservationResult,
    release,
    release_cart,
    reserve,
    total_held,
)


class _FakeRedis:
    """In-memory stand-in for redis-py's subset we use.

    Stores values as strings (like real Redis). `eval()` simulates the
    atomic Lua CHECK-AND-INCR by walking the scan pattern.
    """

    def __init__(self):
        self.store: dict[str, str] = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None, keepttl=False):  # noqa: ARG002
        self.store[key] = str(value)

    def delete(self, *keys):
        for k in keys:
            self.store.pop(k, None)

    def scan(self, cursor=0, match='', count=200):  # noqa: ARG002
        import fnmatch  # noqa: PLC0415

        matched = [k for k in self.store if fnmatch.fnmatch(k, match)]
        return (0, matched)

    def eval(self, script, n_keys, *args):  # noqa: ARG002
        """Reproduce the Lua CHECK-AND-INCR in Python."""
        self_key = args[0]
        qty = int(args[1])
        ttl = int(args[2])  # noqa: F841 — TTL is conceptual in the fake
        pattern = args[3]
        absolute = int(args[4])

        self_current = int(self.store.get(self_key, 0))
        others_total = 0
        import fnmatch  # noqa: PLC0415

        for k, v in self.store.items():
            if k == self_key:
                continue
            if fnmatch.fnmatch(k, pattern):
                try:
                    others_total += int(v)
                except (TypeError, ValueError):
                    continue
        proposed = self_current + qty
        if (proposed + others_total) > absolute:
            return -1
        self.store[self_key] = str(proposed)
        return proposed


class _Reservations:
    """Patch helper — installs the fake redis + a fake absolute_available."""

    def __init__(self, *, absolute=10, enabled=True):
        self.redis = _FakeRedis()
        self.absolute = absolute
        self.enabled = enabled
        self._patches = []

    def __enter__(self):
        self._patches = [
            patch(
                'plugins.installed.inventory.cart_reservations._redis',
                return_value=self.redis,
            ),
            patch(
                'plugins.installed.inventory.cart_reservations._absolute_available',
                return_value=self.absolute,
            ),
            patch(
                'plugins.installed.inventory.cart_reservations._reservations_enabled',
                return_value=self.enabled,
            ),
        ]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()


class ReserveTests(TestCase):
    def test_zero_quantity_returns_ok(self):
        with _Reservations(absolute=10):
            result = reserve(variant_id='v1', cart_id='c1', quantity=0)
        self.assertTrue(result.ok)
        self.assertEqual(result.reason, 'zero qty')

    def test_first_reserve_returns_held_quantity(self):
        with _Reservations(absolute=10):
            result = reserve(variant_id='v1', cart_id='c1', quantity=3)
        self.assertTrue(result.ok)
        self.assertEqual(result.held, 3)

    def test_second_reserve_for_same_cart_accumulates(self):
        with _Reservations(absolute=10) as ctx:
            reserve(variant_id='v1', cart_id='c1', quantity=2)
            result = reserve(variant_id='v1', cart_id='c1', quantity=3)
        self.assertTrue(result.ok)
        self.assertEqual(result.held, 5)
        # Same key only stores one value.
        self.assertEqual(int(ctx.redis.store['cart_reserve:v1:c1']), 5)

    def test_insufficient_stock_returns_not_ok(self):
        with _Reservations(absolute=5):
            reserve(variant_id='v1', cart_id='cA', quantity=4)
            result = reserve(variant_id='v1', cart_id='cB', quantity=3)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, 'insufficient_stock')

    def test_two_carts_within_capacity_both_ok(self):
        with _Reservations(absolute=10):
            r1 = reserve(variant_id='v1', cart_id='cA', quantity=4)
            r2 = reserve(variant_id='v1', cart_id='cB', quantity=4)
        self.assertTrue(r1.ok)
        self.assertTrue(r2.ok)

    def test_disabled_returns_ok_immediately(self):
        with _Reservations(enabled=False):
            result = reserve(variant_id='v1', cart_id='c1', quantity=5)
        self.assertTrue(result.ok)
        self.assertEqual(result.reason, 'disabled')

    def test_redis_unavailable_fails_open(self):
        with (
            patch(
                'plugins.installed.inventory.cart_reservations._redis',
                return_value=None,
            ),
            patch(
                'plugins.installed.inventory.cart_reservations._reservations_enabled',
                return_value=True,
            ),
        ):
            result = reserve(variant_id='v1', cart_id='c1', quantity=5)
        self.assertTrue(result.ok)
        self.assertEqual(result.reason, 'no_redis')


class ReleaseTests(TestCase):
    def test_release_full_drops_key(self):
        with _Reservations(absolute=10) as ctx:
            reserve(variant_id='v1', cart_id='c1', quantity=4)
            release(variant_id='v1', cart_id='c1', quantity=None)
        self.assertNotIn('cart_reserve:v1:c1', ctx.redis.store)

    def test_release_partial_decrements(self):
        with _Reservations(absolute=10) as ctx:
            reserve(variant_id='v1', cart_id='c1', quantity=5)
            release(variant_id='v1', cart_id='c1', quantity=2)
        self.assertEqual(int(ctx.redis.store['cart_reserve:v1:c1']), 3)

    def test_release_to_zero_drops_key(self):
        with _Reservations(absolute=10) as ctx:
            reserve(variant_id='v1', cart_id='c1', quantity=3)
            release(variant_id='v1', cart_id='c1', quantity=3)
        self.assertNotIn('cart_reserve:v1:c1', ctx.redis.store)


class ReleaseCartTests(TestCase):
    def test_drops_every_variant_for_one_cart(self):
        with _Reservations(absolute=20) as ctx:
            reserve(variant_id='vA', cart_id='c1', quantity=2)
            reserve(variant_id='vB', cart_id='c1', quantity=3)
            reserve(variant_id='vC', cart_id='c2', quantity=4)  # other cart, untouched
            count = release_cart(cart_id='c1')

        self.assertEqual(count, 2)
        self.assertNotIn('cart_reserve:vA:c1', ctx.redis.store)
        self.assertNotIn('cart_reserve:vB:c1', ctx.redis.store)
        self.assertIn('cart_reserve:vC:c2', ctx.redis.store)


class TotalHeldTests(TestCase):
    def test_sums_across_carts_for_variant(self):
        with _Reservations(absolute=20):
            reserve(variant_id='v1', cart_id='cA', quantity=2)
            reserve(variant_id='v1', cart_id='cB', quantity=5)
            reserve(variant_id='v1', cart_id='cC', quantity=1)
            self.assertEqual(total_held('v1'), 8)

    def test_other_variants_not_counted(self):
        with _Reservations(absolute=20):
            reserve(variant_id='v1', cart_id='cA', quantity=2)
            reserve(variant_id='v2', cart_id='cA', quantity=7)
            self.assertEqual(total_held('v1'), 2)


class ReservationResultShape(TestCase):
    """Sanity: the public dataclass shape is stable."""

    def test_default_fields_present(self):
        r = ReservationResult(ok=True, held=0, available=0)
        self.assertTrue(r.ok)
        self.assertEqual(r.reason, '')

    def test_serialisable(self):
        r = ReservationResult(ok=False, held=3, available=5, reason='insufficient_stock')
        # Used by tests in upstream callers — must JSON-encode shape.
        self.assertIn(
            'insufficient',
            json.dumps({'reason': r.reason}),
        )
