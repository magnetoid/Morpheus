"""RFM segmentation — quintile scoring on the CDP fields already on Customer
(lifetime_value, purchase_count, last_order_at). No new event capture.

Recomputed nightly. When a customer crosses into a new segment we log a
SegmentMigration row and fire CUSTOMER_SEGMENT_CHANGED so the workflows plugin
can trigger campaigns (e.g. win-back when Loyal → At risk).
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

NEW_WINDOW_DAYS = 30


def classify(r: int, f: int, m: int, purchase_count: int, is_recent: bool) -> str:
    """Map RFM quintile scores → a named segment. Pure + exhaustively tested."""
    if purchase_count <= 1 and is_recent:
        return 'new'
    if r >= 4 and f >= 4 and m >= 4:
        return 'champions'
    if r >= 3 and f >= 3:
        return 'loyal'
    if r <= 2 and f >= 3:
        return 'at_risk'
    if r <= 2 and f <= 2:
        return 'lost'
    return 'potential'


def _quintile_scores(pairs: list) -> dict:
    """pairs = [(key, sortable_value)] → {key: 1-5}. Lowest value → 1, highest → 5."""
    n = len(pairs)
    ordered = sorted(pairs, key=lambda kv: kv[1])
    return {key: 1 + min(4, int(i * 5 / n)) for i, (key, _v) in enumerate(ordered)}


def recompute_all() -> dict:
    """Score every customer with ≥1 order, upsert CustomerSegment, log + fire on flip."""
    from django.contrib.auth import get_user_model

    from core.hooks import MorpheusEvents, hook_registry
    from plugins.installed.customers.models import CustomerSegment, SegmentMigration

    User = get_user_model()
    base = list(
        User.objects.filter(purchase_count__gte=1, last_order_at__isnull=False).values(
            'pk', 'lifetime_value', 'purchase_count', 'last_order_at'
        )
    )
    if not base:
        return {'total': 0, 'changed': 0}

    r_scores = _quintile_scores([(c['pk'], c['last_order_at']) for c in base])
    f_scores = _quintile_scores([(c['pk'], c['purchase_count']) for c in base])
    m_scores = _quintile_scores([(c['pk'], c['lifetime_value']) for c in base])

    now = timezone.now()
    recent_cutoff = now - timedelta(days=NEW_WINDOW_DAYS)
    today = now.date()
    pks = [c['pk'] for c in base]
    existing = {s.customer_id: s for s in CustomerSegment.objects.filter(customer_id__in=pks)}

    changed = 0
    to_create, to_update, migrations = [], [], []
    for c in base:
        pk = c['pk']
        r, f, m = r_scores[pk], f_scores[pk], m_scores[pk]
        is_recent = bool(c['last_order_at'] and c['last_order_at'] >= recent_cutoff)
        seg = classify(r, f, m, c['purchase_count'], is_recent)
        row = existing.get(pk)
        if row is None:
            to_create.append(
                CustomerSegment(customer_id=pk, r_score=r, f_score=f, m_score=m, segment=seg)
            )
            migrations.append(
                SegmentMigration(customer_id=pk, old_segment='', new_segment=seg, day=today)
            )
            changed += 1
        elif row.segment != seg or (row.r_score, row.f_score, row.m_score) != (r, f, m):
            if row.segment != seg:
                # A genuine flip — log it and let subscribers react. The hook
                # contract is customer=<Customer> (core/hooks.py), which the
                # win-back subscriber dereferences (.email/.first_name); passing
                # the bare pk here silently no-op'd every subscriber. Only real
                # flips reach this branch (rare), so the per-flip load is cheap.
                migrations.append(
                    SegmentMigration(
                        customer_id=pk, old_segment=row.segment, new_segment=seg, day=today
                    )
                )
                customer = User.objects.filter(pk=pk).first()
                if customer is not None:
                    hook_registry.fire(
                        MorpheusEvents.CUSTOMER_SEGMENT_CHANGED,
                        customer=customer,
                        old=row.segment,
                        new=seg,
                    )
                changed += 1
            row.r_score, row.f_score, row.m_score, row.segment = r, f, m, seg
            to_update.append(row)

    if to_create:
        CustomerSegment.objects.bulk_create(to_create)
    if to_update:
        CustomerSegment.objects.bulk_update(
            to_update, ['r_score', 'f_score', 'm_score', 'segment', 'computed_at']
        )
    if migrations:
        SegmentMigration.objects.bulk_create(migrations)
    return {'total': len(base), 'changed': changed}
