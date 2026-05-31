"""Experiments runtime — variant assignment + exposure tracking.

API:
  variant_for(request, experiment_key) → str
    Returns the variant name. Cookie-stable; records assignment +
    exposure lazily.

  record_conversion(experiment_key, visitor_id, *, revenue=None)
    Bumps the conversion + revenue counter for the visitor's assigned
    variant. Called from hook subscribers on PURCHASE / ADD_TO_CART
    / etc.

The visitor id comes from either:
  - request.user.pk (authenticated)
  - a long-lived cookie `morph_visitor` (set on first hit)

Statistical layer (lift, significance, sequential testing) is
computed lazily in the dashboard view — no precomputed CIs stored.
"""

from __future__ import annotations

import contextlib
import logging
import secrets
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F

logger = logging.getLogger('morpheus.experiments')

VISITOR_COOKIE = 'morph_visitor'
COOKIE_MAX_AGE = 2 * 365 * 24 * 60 * 60  # 2 years


def visitor_id_for(request) -> str:
    """Stable cookie/session-backed id. Sets the cookie if missing
    (caller is responsible for attaching it to the response — see
    middleware below)."""
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return f'u:{user.pk}'
    cookie = request.COOKIES.get(VISITOR_COOKIE)
    if not cookie:
        cookie = secrets.token_urlsafe(16)
        # Stash on request for middleware to pick up.
        request._set_visitor_cookie = cookie  # type: ignore[attr-defined]
    return f'v:{cookie}'


def variant_for(request, experiment_key: str) -> str:
    """Return the variant name. Records assignment + exposure lazily."""
    from plugins.installed.experiments.models import (  # noqa: PLC0415
        Assignment,
        Experiment,
    )

    try:
        exp = Experiment.objects.filter(key=experiment_key, status='running').first()
        if exp is None:
            return _control_or_empty(experiment_key)

        visitor_id = visitor_id_for(request)
        variant = exp.pick_variant(visitor_id)

        # Lazy write: assignment row + today's exposure bump.
        with contextlib.suppress(IntegrityError):
            Assignment.objects.get_or_create(
                experiment=exp,
                visitor_id=visitor_id,
                defaults={'variant': variant},
            )
        _bump_exposure(exp, variant)
        return variant
    except Exception:  # noqa: BLE001 — never break the page on experiments
        logger.exception('experiments: variant_for failed for %s', experiment_key)
        return _control_or_empty(experiment_key)


def record_conversion(
    *, experiment_key: str, visitor_id: str, revenue: Decimal | None = None
) -> None:
    """Bump conversions + revenue for the visitor's assigned variant.

    No-op if no assignment exists (visitor wasn't in this experiment).
    Safe to call from hook subscribers — wrapped in try/except.
    """
    from plugins.installed.experiments.models import (  # noqa: PLC0415
        Assignment,
        Experiment,
    )

    try:
        exp = Experiment.objects.filter(key=experiment_key).first()
        if exp is None:
            return
        assignment = (
            Assignment.objects.filter(experiment=exp, visitor_id=visitor_id).only('variant').first()
        )
        if assignment is None:
            return
        _bump_conversion(exp, assignment.variant, revenue)
    except Exception:  # noqa: BLE001 — must never break the order pipeline
        logger.exception(
            'experiments: record_conversion failed for %s/%s',
            experiment_key,
            visitor_id,
        )


# ---------------------------------------------------------------------------
# Stats — lift + Wald-interval significance (simple, no SciPy)
# ---------------------------------------------------------------------------


def results_for(experiment) -> dict:
    """Aggregate experiment results with lift + z-score per variant
    against the control (first variant)."""
    from math import sqrt  # noqa: PLC0415

    from plugins.installed.experiments.models import Exposure  # noqa: PLC0415

    rows = (
        Exposure.objects.filter(experiment=experiment)
        .values('variant')
        .annotate(
            exposures=__sum('exposures'),
            conversions=__sum('conversions'),
            revenue=__sum('revenue'),
        )
    )
    by_variant = {r['variant']: r for r in rows}
    names = experiment.variant_names
    if not names:
        return {'variants': []}
    control_name = names[0]
    control = by_variant.get(control_name) or {
        'exposures': 0,
        'conversions': 0,
        'revenue': Decimal('0'),
    }
    control_rate = _rate(control['conversions'], control['exposures'])

    out = []
    for name in names:
        row = by_variant.get(name) or {'exposures': 0, 'conversions': 0, 'revenue': Decimal('0')}
        rate = _rate(row['conversions'], row['exposures'])
        lift = ((rate - control_rate) / control_rate * 100) if control_rate else None
        # Wald two-proportion z-score — good enough for a dashboard
        # signal. The dashboard caveats "n < 1000 → noise" itself.
        se = 0.0
        if (
            control['exposures'] >= 30
            and row['exposures'] >= 30
            and control_rate not in (0, 1)
            and rate not in (0, 1)
        ):
            p_pool = (control['conversions'] + row['conversions']) / (
                control['exposures'] + row['exposures']
            )
            se = sqrt(p_pool * (1 - p_pool) * (1 / control['exposures'] + 1 / row['exposures']))
        z = ((rate - control_rate) / se) if se else None
        out.append(
            {
                'variant': name,
                'is_control': name == control_name,
                'exposures': row['exposures'],
                'conversions': row['conversions'],
                'rate': round(rate * 100, 2),
                'revenue': Decimal(str(row['revenue'])),
                'lift_pct': round(lift, 2) if lift is not None else None,
                'z_score': round(z, 2) if z is not None else None,
                'significant_95': bool(z is not None and abs(z) >= 1.96),
            }
        )

    return {'variants': out, 'control_rate_pct': round(control_rate * 100, 2)}


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _control_or_empty(experiment_key: str) -> str:
    """Return the control variant if the experiment exists in draft/paused/
    concluded state — never None — so calling code can always render."""
    from plugins.installed.experiments.models import Experiment  # noqa: PLC0415

    exp = Experiment.objects.filter(key=experiment_key).only('variants').first()
    if exp and exp.variant_names:
        return exp.variant_names[0]
    return 'control'


def _bump_exposure(experiment, variant: str) -> None:
    from plugins.installed.experiments.models import Exposure  # noqa: PLC0415

    today = date.today()
    with transaction.atomic():
        Exposure.objects.get_or_create(experiment=experiment, variant=variant, day=today)
        Exposure.objects.filter(experiment=experiment, variant=variant, day=today).update(
            exposures=F('exposures') + 1
        )


def _bump_conversion(experiment, variant: str, revenue: Decimal | None) -> None:
    from plugins.installed.experiments.models import Exposure  # noqa: PLC0415

    today = date.today()
    with transaction.atomic():
        Exposure.objects.get_or_create(experiment=experiment, variant=variant, day=today)
        amount = Decimal(str(revenue)) if revenue else Decimal('0')
        Exposure.objects.filter(experiment=experiment, variant=variant, day=today).update(
            conversions=F('conversions') + 1, revenue=F('revenue') + amount
        )


def _rate(num, denom) -> float:
    return (num / denom) if denom else 0.0


def __sum(field):
    from django.db.models import Sum  # noqa: PLC0415

    return Sum(field)
