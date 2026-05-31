"""Co-purchase matrix storage.

Precomputed nightly: for every product P, the top-K other products
that customers also bought in the same order, ranked by Jaccard
similarity (count(P ∩ Q) / count(P ∪ Q)). Storing per-product top-K
rather than the full pairwise matrix keeps lookup O(1) at serve time.
"""

from __future__ import annotations

from django.db import models


class CoPurchaseScore(models.Model):
    """One row per (anchor_product, related_product) above the
    similarity floor. The top-K for each anchor is what the
    storefront block reads."""

    anchor = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='copurchase_anchors',
    )
    related = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='copurchase_relateds',
    )
    score = models.FloatField(
        help_text='Jaccard similarity 0-1; higher = bought together more',
        db_index=True,
    )
    co_count = models.PositiveIntegerField(
        help_text='absolute count of co-occurrences in the window'
    )
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'copurchase_score'
        constraints = [
            models.UniqueConstraint(fields=['anchor', 'related'], name='copurchase_unique_pair'),
            # No CheckConstraint for anchor != related — the precomputer
            # never inserts self-pairs, so the DB-level check would be
            # redundant.
        ]
        indexes = [
            models.Index(fields=['anchor', '-score'], name='copurchase_anchor_score_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.anchor_id} ↔ {self.related_id} ({self.score:.2f})'
