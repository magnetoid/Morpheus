"""A/B experiment storage.

  - Experiment: a named test with variants + weights + status.
  - Assignment: deterministic per visitor (hashed cookie); recorded
    only when the visitor is actually exposed (lazy write).
  - Exposure: append-only count incremented on first render.
  - Conversion: counted via hooks (PURCHASE / ADD_TO_CART / SIGNUP).

The assignment uses MurmurHash3-style mixing (Python's built-in hash
isn't stable across processes) so the same visitor always sees the
same variant. Weights are normalised; default is 50/50.
"""

from __future__ import annotations

import hashlib

from django.db import models

STATUS_CHOICES = (
    ('draft', 'Draft'),
    ('running', 'Running'),
    ('paused', 'Paused'),
    ('concluded', 'Concluded'),
)

GOAL_CHOICES = (
    ('purchase', 'Purchase'),
    ('add_to_cart', 'Add to cart'),
    ('checkout_started', 'Checkout started'),
    ('signup', 'Signup'),
    ('custom', 'Custom event'),
)


class Experiment(models.Model):
    """One A/B test definition."""

    key = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='draft', db_index=True)
    variants = models.JSONField(
        default=list,
        help_text='list[{name: str, weight: int}] — first variant is control',
    )
    goal = models.CharField(max_length=32, choices=GOAL_CHOICES, default='purchase')
    custom_event_name = models.CharField(max_length=120, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    concluded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'experiment'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.key} ({self.status})'

    @property
    def variant_names(self) -> list[str]:
        return [v.get('name', '') for v in (self.variants or [])]

    def pick_variant(self, visitor_id: str) -> str:
        """Deterministic assignment from a stable visitor id (cookie/session)."""
        weights = [int(v.get('weight', 1)) for v in (self.variants or [])]
        names = self.variant_names
        if not weights or not any(weights):
            return names[0] if names else ''
        total = sum(weights)
        h = int.from_bytes(
            hashlib.blake2b(f'{self.key}:{visitor_id}'.encode(), digest_size=8).digest(),
            'big',
        )
        bucket = h % total
        running = 0
        for name, w in zip(names, weights, strict=True):
            running += w
            if bucket < running:
                return name
        return names[-1]


class Assignment(models.Model):
    """Recorded variant per visitor — lazy-written on first exposure."""

    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name='assignments')
    visitor_id = models.CharField(max_length=128, db_index=True)
    variant = models.CharField(max_length=64)
    first_seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'experiment_assignment'
        constraints = [
            models.UniqueConstraint(
                fields=['experiment', 'visitor_id'], name='exp_unique_assignment'
            ),
        ]
        indexes = [
            models.Index(fields=['experiment', 'variant'], name='exp_assign_exp_var_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.experiment_id}:{self.visitor_id[:12]}={self.variant}'


class Exposure(models.Model):
    """Append-only roll-up of exposures + conversions, daily granularity.

    Aggregated into a (experiment, variant, day) row so the dashboard
    can compute lift without scanning millions of raw event rows.
    """

    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name='exposures')
    variant = models.CharField(max_length=64, db_index=True)
    day = models.DateField(db_index=True)
    exposures = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = 'experiment_exposure'
        constraints = [
            models.UniqueConstraint(
                fields=['experiment', 'variant', 'day'], name='exp_exposure_uniq'
            ),
        ]
        ordering = ['-day']

    def __str__(self) -> str:
        return f'{self.experiment_id}:{self.variant}:{self.day}'
