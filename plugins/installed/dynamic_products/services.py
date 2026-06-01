"""dynamic_products — the recommendation engine.

`recommend(block, *, request, customer, context_product=None)` turns a
configured :class:`DynamicBlock` into an ordered, de-duplicated list of
`catalog.Product` instances. One public function; one dispatch table.

Design rules:

* **Fail-soft.** A storefront render must never 500 because a query
  raised. Every strategy is wrapped; on error we return ``[]``.
* **Bounded.** Every queryset is sliced; ``limit`` is clamped to ``MAX``.
* **Cheap.** ``select_related('category')`` + ``prefetch_related('images')``
  on the final fetch so the carousel template never N+1s on price/image.
* **Reuse, don't rebuild.** Behavioral signals come from plugins that
  already record them — analytics (durable views), advanced_ecommerce
  (session recently-viewed), personalisation (precomputed co-purchase).
  Each is imported lazily and optionally; a disabled signal plugin just
  shrinks the candidate pool, it never errors.
"""

# ruff: noqa: PLC0415, S110 — PLC0415: inline imports keep optional signal
#       plugins soft dependencies (importing at module top would hard-couple
#       us to them and break the delete-dir litmus test). S110: the bare
#       try/except/pass guards are intentional — an absent/erroring signal
#       plugin must shrink the pool, never surface. Matches sibling plugins.

from __future__ import annotations

import logging
from collections import Counter

logger = logging.getLogger('morpheus.dynamic_products')

MAX_LIMIT = 24
# How deep to look into history when building affinity / recency signals.
HISTORY_LOOKBACK = 40
PAID_ORDER_STATUSES = ('confirmed', 'processing', 'fulfilled', 'shipped', 'delivered')


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def recommend(block, *, request=None, customer=None, context_product=None) -> list:
    """Return up to ``block.limit`` products for ``block``.

    Never raises into a storefront render — any failure yields ``[]``.
    """
    try:
        limit = max(1, min(int(block.limit or 4), MAX_LIMIT))
    except (TypeError, ValueError):
        limit = 4

    strategy = block.strategy or 'for_you'
    dispatch = {
        'manual': _manual,
        'recently_viewed': _recently_viewed,
        'related': _related,
        'bought_together': _bought_together,
        'for_you': _for_you,
    }
    fn = dispatch.get(strategy, _for_you)

    try:
        ids = fn(
            block, request=request, customer=customer, context_product=context_product, limit=limit
        )
    except Exception:  # noqa: BLE001 — a bad block must not break the page
        logger.warning('dynamic_products: strategy %s failed', strategy, exc_info=True)
        return []

    return _materialize(ids, limit)


# ---------------------------------------------------------------------------
# Strategies — each returns an ORDERED list of product ids (may over-return;
# _materialize de-dupes, drops missing/inactive, and slices to `limit`).
# ---------------------------------------------------------------------------


def _manual(block, *, limit, **_) -> list:
    """Filtered catalog slice: category / tags / metafields, newest first."""
    qs = _base_active_qs()
    qs = _apply_filters(qs, block)
    return list(
        qs.order_by('-is_featured', '-created_at').values_list('pk', flat=True)[: limit * 2]
    )


def _recently_viewed(block, *, request, customer, limit, **_) -> list:
    """Products this visitor recently looked at — session first, then durable."""
    return _recent_view_ids(request, customer, limit=limit * 3)


def _related(block, *, context_product, limit, **_) -> list:
    """Same primary category / shared tags / shared metafields as the PDP product."""
    if context_product is None:
        return []
    return _related_ids(context_product, limit=limit * 2)


def _bought_together(block, *, context_product, customer, limit, **_) -> list:
    """Co-purchase, reusing the personalisation plugin's precomputed scores.

    Falls back to a live OrderItem co-occurrence scan if that plugin is
    absent / has no rows yet for the anchor.
    """
    if context_product is None:
        return []
    ids = _copurchase_ids(context_product, limit=limit * 2)
    if not ids:
        ids = _live_copurchase_ids([context_product.pk], limit=limit * 2)
    return ids


def _for_you(block, *, request, customer, context_product, limit, **_) -> list:
    """The personalized blend — the "best next purchase for this user" path.

    Ranking pool, de-duplicated, then ordered by a simple weighted score:
      * co-purchase off the user's bought/viewed products  (weight 3)
      * recently-viewed                                     (weight 2)
      * products in the user's affinity categories          (weight 1)
    Already-purchased and in-cart products are excluded. Anonymous users
    fall back to popular/featured within their viewed categories, then
    global featured — so the block is never empty on a fresh session.
    """
    purchased = _purchased_ids(customer)
    in_cart = _cart_ids(request, customer)
    exclude = purchased | in_cart
    if context_product is not None:
        exclude.add(context_product.pk)

    score: Counter = Counter()

    # Signal 1 — co-purchase off everything the user has touched.
    seed_ids = list(purchased)[:HISTORY_LOOKBACK]
    recent = _recent_view_ids(request, customer, limit=HISTORY_LOOKBACK)
    seed_ids.extend(recent)
    if seed_ids:
        for pid in _live_copurchase_ids(seed_ids, limit=limit * 4):
            score[pid] += 3

    # Signal 2 — recently viewed (still wants buying).
    for pid in recent:
        score[pid] += 2

    # Signal 3 — category affinity → fill from the user's top categories.
    affinity_cats = _affinity_categories(purchased, recent)
    if affinity_cats:
        cat_qs = _base_active_qs().filter(
            models.Q(category_id__in=affinity_cats)
            | models.Q(additional_categories__in=affinity_cats)
        )
        cat_qs = _apply_filters(cat_qs, block)
        for pid in cat_qs.order_by('-is_featured', '-created_at').values_list('pk', flat=True)[
            : limit * 4
        ]:
            score[pid] += 1

    ranked = [pid for pid, _ in score.most_common() if pid not in exclude]

    # Anonymous / cold-start fallback: popular within viewed categories,
    # then global featured — applying the block's own filters.
    if len(ranked) < limit:
        fallback = _base_active_qs()
        if affinity_cats:
            fallback = fallback.filter(
                models.Q(category_id__in=affinity_cats)
                | models.Q(additional_categories__in=affinity_cats)
            )
        fallback = _apply_filters(fallback, block)
        for pid in fallback.order_by('-is_featured', '-created_at').values_list('pk', flat=True)[
            : limit * 4
        ]:
            if pid not in exclude and pid not in ranked:
                ranked.append(pid)

    return ranked


# ---------------------------------------------------------------------------
# Signal helpers (each optional / lazy / fail-soft)
# ---------------------------------------------------------------------------


def _recent_view_ids(request, customer, *, limit) -> list:
    """Ordered recently-viewed product ids. Session slugs first (freshest,
    works for anonymous), then durable analytics rows for logged-in users."""
    from plugins.installed.catalog.models import Product

    slugs: list[str] = []
    session = getattr(request, 'session', None)
    if session is not None:
        slugs = list(session.get('recently_viewed', []) or [])

    # Durable per-customer history from analytics (optional plugin).
    if customer is not None and getattr(customer, 'is_authenticated', False):
        try:
            from plugins.installed.analytics.models import AnalyticsEvent

            durable = (
                AnalyticsEvent.objects.filter(customer=customer, kind='product_view')
                .exclude(product_slug='')
                .order_by('-created_at')
                .values_list('product_slug', flat=True)[: limit * 2]
            )
            for s in durable:
                if s not in slugs:
                    slugs.append(s)
        except Exception:  # noqa: BLE001 — analytics plugin may be disabled
            pass

    if not slugs:
        return []
    slugs = slugs[:limit]
    by_slug = dict(
        Product.objects.filter(slug__in=slugs, status='active').values_list('slug', 'pk')
    )
    return [by_slug[s] for s in slugs if s in by_slug]


def _related_ids(product, *, limit) -> list:
    """Same primary category → shared tags → shared metafields."""
    out: list = []
    seen: set = {product.pk}

    def _take(qs):
        for pid in qs.values_list('pk', flat=True)[: limit * 2]:
            if pid not in seen:
                seen.add(pid)
                out.append(pid)

    if product.category_id:
        _take(
            _base_active_qs()
            .filter(category_id=product.category_id)
            .exclude(pk=product.pk)
            .order_by('-is_featured', '-created_at')
        )

    if len(out) < limit:
        tag_names = list(product.tags.names())
        if tag_names:
            _take(
                _base_active_qs()
                .filter(tags__name__in=tag_names)
                .exclude(pk=product.pk)
                .distinct()
                .order_by('-is_featured', '-created_at')
            )

    if len(out) < limit:
        _take(_metafield_neighbours_qs(product))

    return out


def _copurchase_ids(product, *, limit) -> list:
    """Reuse the personalisation plugin's precomputed co-purchase scores."""
    try:
        from plugins.installed.personalisation.services import related_to
    except Exception:  # noqa: BLE001 — personalisation plugin not installed
        return []
    try:
        return [p.pk for p in related_to(product, k=limit)]
    except Exception:  # noqa: BLE001
        return []


def _live_copurchase_ids(anchor_ids, *, limit) -> list:
    """Live co-occurrence scan: products that appeared in paid orders
    alongside any of ``anchor_ids``, ranked by co-occurrence count.

    Bounded by HISTORY_LOOKBACK anchors + a sliced OrderItem scan so it's
    safe to call at serve time on a modest catalog.
    """
    if not anchor_ids:
        return []
    from plugins.installed.orders.models import OrderItem

    anchor_set = set(anchor_ids)
    order_ids = list(
        OrderItem.objects.filter(
            product_id__in=anchor_set,
            order__status__in=PAID_ORDER_STATUSES,
        )
        .order_by('-order__placed_at')
        .values_list('order_id', flat=True)[: HISTORY_LOOKBACK * 4]
    )
    if not order_ids:
        return []

    counts: Counter = Counter()
    rows = OrderItem.objects.filter(order_id__in=order_ids).values_list('product_id', flat=True)
    for pid in rows:
        if pid and pid not in anchor_set:
            counts[pid] += 1
    return [pid for pid, _ in counts.most_common(limit)]


def _affinity_categories(purchased_ids, viewed_ids) -> list:
    """Top categories by combined purchase + view weight."""
    from plugins.installed.catalog.models import Product

    pids = list(purchased_ids)[:HISTORY_LOOKBACK] + list(viewed_ids)[:HISTORY_LOOKBACK]
    if not pids:
        return []
    cat_rows = (
        Product.objects.filter(pk__in=pids)
        .exclude(category_id=None)
        .values_list('category_id', flat=True)
    )
    counts = Counter(cat_rows)
    return [cid for cid, _ in counts.most_common(5)]


def _purchased_ids(customer) -> set:
    """Product ids the customer has already bought (any non-cancelled order)."""
    if customer is None or not getattr(customer, 'is_authenticated', False):
        return set()
    from plugins.installed.orders.models import OrderItem

    return set(
        OrderItem.objects.filter(order__customer=customer)
        .exclude(order__status__in=('cancelled', 'refunded'))
        .values_list('product_id', flat=True)
    )


def _cart_ids(request, customer) -> set:
    """Product ids currently in the visitor's cart (session or customer)."""
    from plugins.installed.orders.models import Cart

    cart = None
    try:
        if customer is not None and getattr(customer, 'is_authenticated', False):
            cart = Cart.objects.filter(customer=customer).order_by('-updated_at').first()
        if cart is None:
            session = getattr(request, 'session', None)
            key = getattr(session, 'session_key', None) if session is not None else None
            if key:
                cart = Cart.objects.filter(session_key=key).order_by('-updated_at').first()
    except Exception:  # noqa: BLE001
        return set()
    if cart is None:
        return set()
    return set(cart.items.values_list('product_id', flat=True))


# ---------------------------------------------------------------------------
# Querysets + filters
# ---------------------------------------------------------------------------


def _base_active_qs():
    from plugins.installed.catalog.models import Product

    return Product.objects.filter(status='active')


def _apply_filters(qs, block):
    """Apply a block's declarative category / tag / metafield filters."""
    cat_ids = list(block.categories.values_list('pk', flat=True))
    if cat_ids:
        qs = qs.filter(
            models.Q(category_id__in=cat_ids) | models.Q(additional_categories__in=cat_ids)
        ).distinct()

    tags = block.tags or []
    if isinstance(tags, list) and tags:
        qs = qs.filter(tags__name__in=tags).distinct()

    if block.metafield_key:
        mf_ids = _metafield_product_ids(block.metafield_key, block.metafield_value)
        if mf_ids is not None:
            qs = qs.filter(pk__in=mf_ids)

    return qs


def _metafield_product_ids(key, value):
    """Product ids carrying ``key`` (and ``value`` if given). Returns None
    when the metafields plugin is absent so the caller skips the filter."""
    try:
        from django.contrib.contenttypes.models import ContentType

        from plugins.installed.catalog.models import Product
        from plugins.installed.metafields.models import Metafield
    except Exception:  # noqa: BLE001 — metafields plugin not installed
        return None
    ct = ContentType.objects.get_for_model(Product)
    rows = Metafield.objects.filter(content_type=ct, key=key)
    if value:
        rows = rows.filter(value=value)
    return list(rows.values_list('object_id', flat=True))


def _metafield_neighbours_qs(product):
    """Other active products sharing any of ``product``'s metafield (key,value)."""
    try:
        from django.contrib.contenttypes.models import ContentType

        from plugins.installed.catalog.models import Product
        from plugins.installed.metafields.models import Metafield
    except Exception:  # noqa: BLE001
        return _base_active_qs().none()
    ct = ContentType.objects.get_for_model(Product)
    pairs = list(
        Metafield.objects.filter(content_type=ct, object_id=str(product.pk)).values_list(
            'key', 'value'
        )
    )
    if not pairs:
        return _base_active_qs().none()
    q = models.Q()
    for key, val in pairs:
        q |= models.Q(key=key, value=val)
    neighbour_ids = (
        Metafield.objects.filter(content_type=ct)
        .filter(q)
        .exclude(object_id=str(product.pk))
        .values_list('object_id', flat=True)
    )
    return (
        _base_active_qs().filter(pk__in=list(neighbour_ids)).order_by('-is_featured', '-created_at')
    )


def _materialize(ids, limit) -> list:
    """De-dupe (preserving order), fetch active products, slice to limit."""
    from plugins.installed.catalog.models import Product

    seen: set = set()
    ordered: list = []
    for pid in ids:
        if pid not in seen:
            seen.add(pid)
            ordered.append(pid)
        if len(ordered) >= limit:
            break
    if not ordered:
        return []
    by_id = {
        p.pk: p
        for p in (
            Product.objects.filter(pk__in=ordered, status='active')
            .select_related('category')
            .prefetch_related('images')
        )
    }
    return [by_id[pid] for pid in ordered if pid in by_id]


# `models` is imported lazily-at-module-scope only for Q() expressions used
# in the filter helpers; keep it here so those helpers read naturally.
from django.db import models  # noqa: E402
