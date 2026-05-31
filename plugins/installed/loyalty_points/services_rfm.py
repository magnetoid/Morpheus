"""RFM (Recency / Frequency / Monetary) segmentation.

Each axis is bucketed 1-5 via quintile splits across the customer
base. The composite key (e.g. '555') maps to a named segment that
email + storefront automation can target:

  555  → champion        (most recent, most frequent, biggest spend)
  544  → loyal
  4xx  → promising
  3xx  → at_risk
  2xx  → hibernating
  1xx  → lost
  ?-5  → new              (recently signed up, no F/M data yet)

The mapping is intentionally simple — we surface the segment, the
email plugin + storefront blocks decide what offer each gets.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Sum
from django.utils import timezone

logger = logging.getLogger('morpheus.loyalty.rfm')


def compute_all() -> dict:
    """Nightly task: compute R/F/M for every customer with at least one
    order in the last 24 months. Returns segment counts.
    """
    from plugins.installed.loyalty_points.models import CustomerRFM  # noqa: PLC0415
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    cutoff = timezone.now() - timedelta(days=730)
    base = Order.objects.filter(
        placed_at__gte=cutoff,
        customer_id__isnull=False,
        status__in=('confirmed', 'paid', 'fulfilled', 'completed'),
    )

    per_customer = list(
        base.values('customer_id').annotate(
            last_order=Max('placed_at'),
            order_count=Count('id'),
            revenue=Sum('total'),
        )
    )
    if not per_customer:
        return {}

    now = timezone.now()
    # Materialise the three axes for quintile splitting.
    recency_days = [(row['customer_id'], (now - row['last_order']).days) for row in per_customer]
    frequency = [(row['customer_id'], row['order_count']) for row in per_customer]
    monetary = [(row['customer_id'], Decimal(str(row['revenue'] or 0))) for row in per_customer]

    r_lookup = _quintile_scores(recency_days, ascending=True)
    f_lookup = _quintile_scores(frequency, ascending=False)
    m_lookup = _quintile_scores(monetary, ascending=False)

    counts: dict[str, int] = {}
    for row in per_customer:
        cid = row['customer_id']
        r = r_lookup.get(cid, 3)
        f = f_lookup.get(cid, 3)
        m = m_lookup.get(cid, 3)
        composite = f'{r}{f}{m}'
        segment = _segment_for(r, f, m)
        CustomerRFM.objects.update_or_create(
            customer_id=cid,
            defaults={
                'r_score': r,
                'f_score': f,
                'm_score': m,
                'composite': composite,
                'segment': segment,
            },
        )
        counts[segment] = counts.get(segment, 0) + 1

    logger.info('loyalty.rfm: segments computed %s', counts)
    return counts


def segment_for_customer(customer) -> str | None:
    """Read-only — return the cached segment or None if uncomputed."""
    from plugins.installed.loyalty_points.models import CustomerRFM  # noqa: PLC0415

    row = CustomerRFM.objects.filter(customer=customer).only('segment').first()
    return row.segment if row else None


# ---------------------------------------------------------------------------


def _quintile_scores(pairs: list[tuple], *, ascending: bool) -> dict:
    """Bucket the (customer_id, value) pairs into quintiles 1-5.

    `ascending=True` means smaller value → higher score (recency: fewer
    days since last order is better). `ascending=False` means larger
    value → higher score (frequency, monetary).
    """
    if not pairs:
        return {}
    sorted_pairs = sorted(pairs, key=lambda p: p[1], reverse=not ascending)
    n = len(sorted_pairs)
    # Top quintile gets score 5, second 4, ..., bottom 1.
    out: dict = {}
    for idx, (cid, _val) in enumerate(sorted_pairs):
        quintile = min(4, idx * 5 // n)  # 0..4
        out[cid] = 5 - quintile  # invert so top = 5
    return out


def _segment_for(r: int, f: int, m: int) -> str:
    """Map (R, F, M) ∈ [1,5]³ → one of the seven named segments."""
    if r == 5 and f == 5 and m == 5:
        return 'champion'
    if r >= 4 and f >= 4:
        return 'loyal'
    if r >= 4:
        return 'promising'
    if r == 3:
        return 'at_risk'
    if r == 2:
        return 'hibernating'
    return 'lost'


def is_new_customer(customer) -> bool:
    """Recent signup with too little history to RFM-score sensibly."""
    User = get_user_model()  # noqa: N806
    try:
        u = User.objects.only('date_joined').get(pk=customer.pk)
    except User.DoesNotExist:
        return False
    return (timezone.now() - u.date_joined).days < 30
