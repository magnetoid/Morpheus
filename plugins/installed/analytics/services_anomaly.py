"""Metric anomaly detection v1 — robust z-score against a same-weekday
baseline (falls back to trailing-14-days when history is thin). Pure
Python `statistics`, no deps; conservative defaults so it alerts on
broken-checkout-grade shifts, not noise."""

from __future__ import annotations

import statistics
from datetime import date, timedelta

from django.utils import timezone

# metric name → how to read its value off a DailyMetric row
_WATCHED = ('revenue', 'orders', 'sessions', 'conversion_rate')
_Z_THRESHOLD = 3.0
_MIN_POINTS = 7


def _value(row) -> float:
    if row.metric == 'revenue':
        money = row.value_money
        return float(money.amount) if money is not None else 0.0
    return float(row.value_int)


def _baseline_rows(metric: str, target: date):
    from plugins.installed.analytics.models import DailyMetric  # noqa: PLC0415

    # Preferred: the same weekday over the trailing 8 weeks.
    same_weekday = [target - timedelta(weeks=w) for w in range(1, 9)]
    rows = list(DailyMetric.objects.filter(metric=metric, dimension='', day__in=same_weekday))
    if len(rows) >= 4:
        return rows
    # Thin history: trailing 14 days.
    return list(
        DailyMetric.objects.filter(
            metric=metric,
            dimension='',
            day__gte=target - timedelta(days=14),
            day__lt=target,
        )
    )


def detect_anomalies(*, day: date | None = None) -> list[dict]:
    """Scan watched metrics for `day` (default yesterday). Returns findings
    and records one idempotent analytics.anomaly event per (metric, day);
    notifies staff fail-soft."""
    from plugins.installed.analytics.models import DailyMetric  # noqa: PLC0415
    from plugins.installed.analytics.services import record_event  # noqa: PLC0415

    target = day or (timezone.now().date() - timedelta(days=1))
    findings: list[dict] = []
    for metric in _WATCHED:
        today_row = DailyMetric.objects.filter(metric=metric, dimension='', day=target).first()
        if today_row is None:
            continue
        baseline = _baseline_rows(metric, target)
        if len(baseline) < _MIN_POINTS - 1 and len(baseline) < 4:
            continue  # not enough history to judge
        values = [_value(r) for r in baseline]
        med = statistics.median(values)
        mad = statistics.median(abs(v - med) for v in values)
        # Robust sigma; guard the all-identical case with a tiny floor
        # proportional to the median so a flat-but-nonzero series with one
        # dead day still fires.
        sigma = 1.4826 * mad if mad else max(abs(med) * 0.05, 1.0)
        x = _value(today_row)
        z = (x - med) / sigma if sigma else 0.0
        if abs(z) < _Z_THRESHOLD:
            continue
        direction = 'down' if z < 0 else 'up'
        summary = (
            f'{metric} was {x:,.2f} vs a typical {med:,.2f} (z={z:+.1f}) on {target.isoformat()}'
        )
        finding = {
            'metric': metric,
            'day': target.isoformat(),
            'value': x,
            'baseline': med,
            'z': round(z, 2),
            'direction': direction,
            'summary': summary,
        }
        findings.append(finding)

        # Idempotent event for the activity feed (max 1 per metric/day).
        record_event(
            name='analytics.anomaly',
            kind='custom',
            payload=finding,
            idempotency_key=f'anomaly:{metric}:{target.isoformat()}',
        )

    if findings:
        _notify(findings)
    return findings


def _notify(findings: list[dict]) -> None:
    """Staff notification via notifications_center — best-effort."""
    try:
        from plugins.installed.notifications_center.services import (  # noqa: PLC0415
            notify_all_staff,
        )
    except ImportError:
        return
    try:
        titles = ', '.join(f['metric'] for f in findings)
        notify_all_staff(
            kind='analytics.anomaly',
            title=f'Metric anomaly: {titles}',
            body='\n'.join(f['summary'] for f in findings),
            action_url='/dashboard/analytics/v2/',
            icon='alert-triangle',
        )
    except Exception:  # noqa: BLE001, S110 — alerting must never crash the beat
        pass
