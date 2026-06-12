"""Rails models — merchant-curated product lists for each rail.

`CuratedRail` lets the merchant (or Linda, given the curator scope)
pin specific products to a slot (e.g. "this week, the For You rail
should lead with the new arrival"). The fallback resolver in
`services.resolve_rail()` reads personalisation signals; the curated
list takes precedence.
"""

from __future__ import annotations

from morpheus import models


class CuratedRail(models.Model):
    """A merchant-curated list of products for a single rail slot."""

    slug = models.CharField(max_length=64, unique=True, db_index=True)
    title = models.CharField(max_length=120, blank=True)
    products = models.ManyToManyField(
        'catalog.Product',
        related_name='curated_in_rails',
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['slug']

    def __str__(self) -> str:
        return self.title or self.slug
