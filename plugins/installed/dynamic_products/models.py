"""dynamic_products — models.

One table: ``DynamicBlock``. Each row is a merchant-configured slice of
personalized merchandising: *render this strategy, in this theme slot,
filtered like so, headed with this copy.* The storefront block templates
read enabled rows for their slot; the engine in ``services.py`` turns a
row into a ranked list of products.

No view-tracking model lives here on purpose. The durable behavioral
signal Morpheus already records is reused (see ``services.py``):

* ``analytics.AnalyticsEvent`` rows with ``kind='product_view'`` — written
  by the analytics plugin from the ``product.viewed`` hook + storefront
  pageview middleware. Carries ``customer``, ``session`` and
  ``product_slug``.
* ``request.session['recently_viewed']`` — a short slug list maintained by
  the ``advanced_ecommerce`` plugin's ``product.viewed`` subscriber.

Rebuilding a third view table would duplicate both. If neither plugin is
active the engine degrades gracefully to catalog-only strategies.
"""

from __future__ import annotations

import uuid

from django.db import models

# Theme slots the reference theme (dot_books) renders today. Mirrors the
# canonical catalog in docs/THEME_DEVELOPMENT.md §6 — keep in sync.
SLOT_CHOICES = [
    ('home_above_grid', 'Home — above the grid'),
    ('home_below_grid', 'Home — below the grid'),
    ('pdp_below_price', 'Product page — below price'),
    ('pdp_below_form', 'Product page — below add-to-cart'),
    ('pdp_above_long_description', 'Product page — above description'),
    ('cart_summary_extra', 'Cart — order summary'),
    ('global_below_body', 'Every page — end of body'),
]

# Strategies the engine implements (see services.recommend()).
STRATEGY_CHOICES = [
    ('for_you', 'For you (personalized blend)'),
    ('manual', 'Manual / rule (filtered catalog)'),
    ('recently_viewed', 'Recently viewed'),
    ('related', 'Related to this product'),
    ('bought_together', 'Frequently bought together'),
    ('probability_grid', 'Dynamic Probability Grid'),
]

# Strategies that only make sense on a product page (need context_product).
PDP_ONLY_STRATEGIES = {'related', 'bought_together'}


class DynamicBlock(models.Model):
    """A merchant-configured dynamic merchandising block.

    Rendered into ``slot`` by ``contribute_storefront_blocks`` when
    ``enabled``. The engine resolves ``strategy`` (optionally narrowed by
    the filter fields) into a ranked, de-duplicated product list capped at
    ``limit``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(
        max_length=120,
        help_text='Internal label shown in the dashboard list. Not shown to shoppers.',
    )
    heading = models.CharField(
        max_length=160,
        blank=True,
        help_text='Shopper-facing carousel heading, e.g. "Picked for you".',
    )
    slot = models.CharField(
        max_length=40,
        choices=SLOT_CHOICES,
        db_index=True,
        help_text='Where on the storefront this block renders.',
    )
    strategy = models.CharField(
        max_length=20,
        choices=STRATEGY_CHOICES,
        default='for_you',
        help_text='How products are chosen.',
    )
    limit = models.PositiveSmallIntegerField(
        default=4,
        help_text='Maximum number of products to show (1–24).',
    )
    enabled = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveSmallIntegerField(
        default=50,
        help_text='Render order within a slot — lower shows first.',
    )

    # ── Filter fields (apply to manual/for_you; ignored by pure context
    #    strategies). Stored declaratively so a block needs no code. ──────
    categories = models.ManyToManyField(
        'catalog.Category',
        blank=True,
        related_name='dynamic_blocks',
        help_text='Restrict to these categories (plus their primary/additional listings).',
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text='Restrict to products carrying any of these tag names, e.g. ["sale", "new"].',
    )
    metafield_key = models.CharField(
        max_length=120,
        blank=True,
        help_text='Restrict to products with this metafield key (requires the metafields plugin).',
    )
    metafield_value = models.CharField(
        max_length=255,
        blank=True,
        help_text='…and this metafield value. Leave blank to match any value for the key.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['slot', 'sort_order', 'name']
        indexes = [
            # Hot path: storefront fetch "enabled blocks for this slot".
            models.Index(
                fields=['slot', 'enabled', 'sort_order'], name='dynblock_slot_enabled_idx'
            ),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.get_strategy_display()} → {self.slot})'

    @property
    def is_pdp_only(self) -> bool:
        return self.strategy in PDP_ONLY_STRATEGIES


class DynamicGridItem(models.Model):
    """Stores all book metadata and a real-time calculated purchase probability score
    for dynamic grid layout rendering.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.OneToOneField(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='dynamic_grid_item'
    )
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True)
    cover_image_url = models.URLField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    genre = models.CharField(max_length=100, blank=True)
    
    # Real-time calculated purchase probability score (0.0 to 1.0)
    purchase_probability = models.FloatField(default=0.0, db_index=True)
    
    last_calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-purchase_probability']

    def __str__(self) -> str:
        return f"{self.title} (Probability: {self.purchase_probability:.2f})"

