"""Demand forecasting + reorder alerts.

Approach (deliberately simple — beats LLM forecasting at our scale):

  1. For each variant, compute the rolling N-day velocity from
     StockMovement('sale') rows: total units sold / N.
  2. Days-until-stockout = current available_quantity / velocity.
  3. Surface every variant with DAYS_UNTIL_STOCKOUT < REORDER_THRESHOLD
     (default 14 days) as an alert with a recommended reorder quantity.

Why not LLM forecasting (yet):
  - For < 10k SKUs and < 1k orders/day, EMA/SMA beats LLM-based
    forecasting on both accuracy and cost.
  - The signal here is "you should look at this SKU" — humans/AI can
    do the demand-shaping work; we just need to surface the right
    candidates.
  - When we ship the self-improvement engine analyzer (Phase 1
    Increment 4), it can layer LLM reasoning on top of these alerts
    to suggest reorder quantities adjusted for seasonality, promo
    history, etc.

The alerts feed into the self-improvement signal bus as
`source='code_quality'` rows (TODO: add a dedicated `demand` source
in Phase 2 — for now we piggyback on the existing infrastructure
since the dashboard treats every signal source identically).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db.models import F, Sum
from django.utils import timezone

logger = logging.getLogger('morpheus.inventory.demand_forecast')

# Rolling window for velocity. 28 days catches monthly seasonality
# without being so long that recent trend changes get washed out.
DEFAULT_WINDOW_DAYS = 28
DEFAULT_REORDER_THRESHOLD_DAYS = 14
# Multiplier on (window_days × velocity) to suggest a reorder size —
# default 2× the window so you cover the next equivalent window plus
# safety stock.
DEFAULT_REORDER_MULTIPLIER = 2.0


@dataclass(slots=True)
class ForecastRow:
    """One forecast per variant."""

    variant_id: str
    variant_label: str
    available: int
    daily_velocity: float
    days_until_stockout: float | None  # None = no velocity, infinite
    reorder_recommended: bool
    suggested_reorder_qty: int
    sold_in_window: int
    window_days: int
    overstocked: bool = False


def forecast_all(
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    threshold_days: int = DEFAULT_REORDER_THRESHOLD_DAYS,
    reorder_multiplier: float = DEFAULT_REORDER_MULTIPLIER,
) -> list[ForecastRow]:
    """Compute forecast rows for every tracked variant.

    Cheap enough at < 100k SKUs to run synchronously; for larger
    catalogs the per-row computation should move to a Celery task
    paginating in batches of 1000.
    """
    from plugins.installed.catalog.models import ProductVariant  # noqa: PLC0415
    from plugins.installed.inventory.models import StockLevel, StockMovement  # noqa: PLC0415

    cutoff = timezone.now() - timedelta(days=window_days)

    # 1. Per-variant available quantity from StockLevel (sum across warehouses).
    available_by_variant: dict[str, int] = defaultdict(int)
    for row in StockLevel.objects.values('variant_id').annotate(
        total=Sum(F('quantity') - F('reserved_quantity'))
    ):
        available_by_variant[str(row['variant_id'])] = max(0, int(row['total'] or 0))

    # 2. Per-variant rolling-window sales from StockMovement('sale').
    sales_by_variant: dict[str, int] = defaultdict(int)
    sale_rows = (
        StockMovement.objects.filter(
            movement_type='sale',
            created_at__gte=cutoff,
        )
        .values('stock_level__variant_id')
        .annotate(total=Sum('quantity_change'))
    )
    for row in sale_rows:
        vid = str(row['stock_level__variant_id'])
        # StockMovement.quantity_change is negative for sales — normalise.
        sales_by_variant[vid] = abs(int(row['total'] or 0))

    # 3. Build the forecast rows for every variant that exists in either map.
    out: list[ForecastRow] = []
    variant_ids = set(available_by_variant) | set(sales_by_variant)
    if not variant_ids:
        return out

    # Pull variant labels in one query (avoid N+1).
    variant_labels = {
        str(v.pk): _variant_label(v)
        for v in ProductVariant.objects.filter(pk__in=variant_ids).select_related('product')
    }

    for vid in variant_ids:
        sold = sales_by_variant.get(vid, 0)
        velocity = sold / window_days if window_days > 0 else 0.0
        available = available_by_variant.get(vid, 0)

        days_until = round(available / velocity, 1) if velocity > 0 else None

        reorder = days_until is not None and days_until < threshold_days
        suggested = int(velocity * window_days * reorder_multiplier) if reorder else 0

        out.append(
            ForecastRow(
                variant_id=vid,
                variant_label=variant_labels.get(vid, vid[:12]),
                available=available,
                daily_velocity=round(velocity, 2),
                days_until_stockout=days_until,
                reorder_recommended=reorder,
                suggested_reorder_qty=suggested,
                sold_in_window=sold,
                window_days=window_days,
            )
        )

    # Overstock flag: has stock, at-or-below the median velocity, and >90 days of
    # cover (or no velocity at all — dead stock). Additive; existing callers ignore it.
    velocities = sorted(r.daily_velocity for r in out if r.daily_velocity > 0)
    median_v = velocities[len(velocities) // 2] if velocities else 0.0
    for r in out:
        r.overstocked = bool(
            r.available > 0
            and r.daily_velocity <= median_v
            and (r.days_until_stockout is None or r.days_until_stockout > 90)
        )

    # Sort reorders-first, then by days-until-stockout ascending.
    out.sort(
        key=lambda r: (
            not r.reorder_recommended,
            r.days_until_stockout if r.days_until_stockout is not None else 10**9,
        )
    )
    return out


def emit_reorder_signals(
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    threshold_days: int = DEFAULT_REORDER_THRESHOLD_DAYS,
) -> int:
    """Feed reorder candidates into the self-improvement signal bus.

    One signal per variant that's projected to stock out within
    `threshold_days`. The dashboard can group these into a single
    recommendation per SKU class (e.g. "5 variants from publisher X
    are running low").
    """
    try:
        from core.self_improvement.services import (  # noqa: PLC0415
            emit_signal,
            fingerprint_for,
        )
    except ImportError:
        logger.warning('demand_forecast: self_improvement not installed; skipping signals')
        return 0

    rows = forecast_all(window_days=window_days, threshold_days=threshold_days)
    emitted = 0
    for row in rows:
        if not row.reorder_recommended:
            continue
        try:
            emit_signal(
                source='code_quality',  # placeholder; dedicated `demand` source comes in Phase 2
                fingerprint=fingerprint_for('demand', row.variant_id),
                severity=_severity_for(row),
                payload={
                    'tool': 'demand_forecast',
                    'rule': 'low_stock_reorder',
                    'variant_id': row.variant_id,
                    'variant_label': row.variant_label,
                    'available': row.available,
                    'daily_velocity': row.daily_velocity,
                    'days_until_stockout': row.days_until_stockout,
                    'suggested_reorder_qty': row.suggested_reorder_qty,
                    'window_days': row.window_days,
                    'sold_in_window': row.sold_in_window,
                },
            )
            emitted += 1
        except Exception:  # noqa: BLE001
            logger.exception('demand_forecast: emit_signal failed for variant=%s', row.variant_id)
    return emitted


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _variant_label(variant) -> str:
    name = getattr(variant, 'name', '') or ''
    product_name = getattr(getattr(variant, 'product', None), 'name', '') or ''
    if product_name and name:
        return f'{product_name} — {name}'[:200]
    return (product_name or name or str(variant.pk))[:200]


def _severity_for(row: ForecastRow) -> int:
    """Higher severity = closer to stockout."""
    if row.days_until_stockout is None:
        return 30
    if row.days_until_stockout < 3:
        return 90
    if row.days_until_stockout < 7:
        return 75
    if row.days_until_stockout < 14:
        return 60
    return 45


# ---------------------------------------------------------------------------
# Cost helpers — for ROI display on the dashboard later
# ---------------------------------------------------------------------------


def projected_lost_revenue_if_no_reorder(row: ForecastRow, unit_price: Decimal) -> Decimal:
    """Naive: window_days × velocity × unit_price, capped by current stock.

    Used by the dashboard to surface "$X potential lost revenue this
    month if you don't reorder". Not authoritative — just a rough
    motivator for the merchant to act.
    """
    if row.daily_velocity <= 0 or unit_price is None:
        return Decimal('0')
    days = max(0, row.window_days - (row.days_until_stockout or 0))
    units_lost = round(row.daily_velocity * days)
    return Decimal(str(unit_price)) * Decimal(str(units_lost))


def sync_stockout_alerts(
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    threshold_days: int = DEFAULT_REORDER_THRESHOLD_DAYS,
) -> dict:
    """Reconcile the forecast against open StockoutAlerts.

    Opens an alert for each newly at-risk variant, refreshes the snapshot of
    ones still at risk, and resolves ones that have recovered. Returns
    {'opened': [StockoutAlert, ...], 'refreshed': int, 'resolved': int}.
    """
    from django.utils import timezone  # noqa: PLC0415

    from plugins.installed.inventory.models import StockoutAlert  # noqa: PLC0415

    rows = forecast_all(window_days=window_days, threshold_days=threshold_days)
    at_risk = {str(r.variant_id): r for r in rows if r.reorder_recommended}
    open_alerts = {str(a.variant_id): a for a in StockoutAlert.objects.filter(status='open')}

    opened: list = []
    refreshed = 0
    for vid, row in at_risk.items():
        existing = open_alerts.get(vid)
        if existing is not None:
            existing.days_of_cover = row.days_until_stockout
            existing.daily_velocity = row.daily_velocity
            existing.suggested_reorder_qty = row.suggested_reorder_qty
            existing.save(
                update_fields=[
                    'days_of_cover',
                    'daily_velocity',
                    'suggested_reorder_qty',
                    'last_seen_at',
                ]
            )
            refreshed += 1
        else:
            # get_or_create (not create) so concurrent runs can't IntegrityError
            # on the one-open-alert-per-variant partial unique constraint.
            alert, created = StockoutAlert.objects.get_or_create(
                variant_id=row.variant_id,
                status='open',
                defaults={
                    'days_of_cover': row.days_until_stockout,
                    'daily_velocity': row.daily_velocity,
                    'suggested_reorder_qty': row.suggested_reorder_qty,
                },
            )
            if created:
                opened.append(alert)

    resolved = 0
    for vid, alert in open_alerts.items():
        if vid not in at_risk:
            alert.status = 'resolved'
            alert.resolved_at = timezone.now()
            alert.save(update_fields=['status', 'resolved_at'])
            resolved += 1

    return {'opened': opened, 'refreshed': refreshed, 'resolved': resolved}
