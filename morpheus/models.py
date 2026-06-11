"""ORM primitives for plugin authors.

Re-exports the Django ORM surface plugin authors need plus the third-
party bits we treat as first-class (djmoney). Plugin code should::

    from morpheus import models

    class Coupon(models.Model):
        code = models.CharField(max_length=32, unique=True)
        amount = models.MoneyField(max_digits=14, decimal_places=2,
                                   default_currency='USD')

…instead of importing from ``django.db.models`` and ``djmoney``
separately.
"""

from __future__ import annotations

# Wildcard-import is the natural fit here — `morpheus.models` is a
# drop-in replacement for `django.db.models`, so we want every public
# name (`Model`, `CharField`, `ForeignKey`, `Q`, `F`, `Index`, …) to
# come along.
from django.db.models import *  # noqa: F401, F403
from django.db.models import (  # noqa: F401 — re-export for convenience
    Avg,
    Count,
    F,
    Index,
    Manager,
    Max,
    Min,
    Model,
    Q,
    QuerySet,
    Sum,
)
from djmoney.models.fields import MoneyField  # noqa: F401
from djmoney.money import Money  # noqa: F401
