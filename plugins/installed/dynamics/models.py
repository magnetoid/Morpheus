"""dynamics — models.

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

from django.conf import settings
from django.db import models

# Theme slots the reference theme (dot_books) renders today. Mirrors the
# canonical catalog in docs/THEME_DEVELOPMENT.md §6 — keep in sync.
SLOT_CHOICES = [
    ('home_above_grid', 'Home — above the grid'),
    ('home_below_grid', 'Home — below the grid'),
    ('home_after_rails', 'Home — after the collection rails'),
    ('pdp_below_price', 'Product page — below price'),
    ('pdp_below_form', 'Product page — below add-to-cart'),
    ('pdp_above_long_description', 'Product page — above description'),
    ('cart_summary_extra', 'Cart — order summary'),
    ('checkout_extra', 'Checkout — below the form'),
    ('order_receipt_extra', 'Order confirmation — below the receipt'),
    ('global_below_body', 'Every page — end of body'),
]

# Named theme placeholders (existing page furniture) a block can TAKE OVER via
# the STOREFRONT_PRODUCTS hook — unlike slots, these don't render a new
# carousel; they decide what fills a list the theme already renders.
# free = dynamics picks the products; reorder = dynamics only reorders the
# view's default list (paginated slices keep their filter semantics).
SURFACE_CHOICES = [
    ('home_hero', 'Home — hero carousel (free pick)'),
    ('home_featured', 'Home — “New & notable” grid (free pick)'),
    ('home_staff_picks', 'Home — staff picks grid (reorder)'),
    ('plp_default', 'Shop — default product list (reorder, per page)'),
    ('category_list', 'Category pages (reorder, per page)'),
    ('collection_list', 'Collection pages (reorder, per page)'),
    ('section_featured', 'Page-builder “Featured products” sections (reorder)'),
]

# Surfaces where dynamics may freely choose products (vs reorder-only).
FREE_PICK_SURFACES = {'home_hero', 'home_featured'}

# Strategies the engine implements (see services.recommend()).
STRATEGY_CHOICES = [
    ('smart', 'Smart (probability + trend + session, explainable)'),
    ('for_you', 'For you (personalized blend)'),
    ('manual', 'Manual / rule (filtered catalog)'),
    ('recently_viewed', 'Recently viewed'),
    ('related', 'Related to this product'),
    ('bought_together', 'Frequently bought together'),
    ('probability_grid', 'Dynamic Probability Grid'),
    ('autopilot', 'Autopilot (self-optimizing, per-visitor)'),
    ('trending', 'Trending now'),
    ('new_arrivals', 'New arrivals'),
    ('best_sellers', 'Best sellers'),
    ('on_sale', 'On sale'),
    ('similar_price', 'Similar price (product page)'),
]

# Strategies that only make sense on a product page (need context_product).
PDP_ONLY_STRATEGIES = {'related', 'bought_together', 'similar_price'}


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
        blank=True,
        help_text='Where on the storefront this block renders (leave empty for a surface takeover).',
    )
    surface = models.CharField(
        max_length=40,
        choices=SURFACE_CHOICES,
        blank=True,
        default='',
        db_index=True,
        help_text=(
            'Existing theme placeholder this block takes over (hero, featured '
            'grid, PLP order, …). Leave empty for a normal slot block.'
        ),
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

    # ── Extra filter options (B2) ────────────────────────────────────────────
    exclude_out_of_stock = models.BooleanField(
        default=False,
        help_text='Hide products with zero available stock (needs the inventory plugin).',
    )
    exclude_purchased = models.BooleanField(
        default=False, help_text='Hide products the signed-in visitor has already bought.'
    )
    price_min = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Only show products at/above this price.',
    )
    price_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Only show products at/below this price.',
    )
    pinned_product_ids = models.JSONField(
        default=list, blank=True, help_text='Product ids to force to the front, in order.'
    )
    excluded_product_ids = models.JSONField(
        default=list, blank=True, help_text='Product ids to always hide from this block.'
    )

    # ── Display options (B3) ─────────────────────────────────────────────────
    LAYOUT_CHOICES = [('carousel', 'Carousel'), ('grid', 'Grid')]
    layout = models.CharField(max_length=16, choices=LAYOUT_CHOICES, default='carousel')
    columns = models.PositiveSmallIntegerField(
        default=4, help_text='Items per row when the layout is Grid (2–6).'
    )
    show_price = models.BooleanField(default=True)
    show_title = models.BooleanField(
        default=True, help_text='Show the product name under each cover (off = image-only grid).'
    )
    show_reason = models.BooleanField(
        default=False, help_text='Show a short "why" label under each product (e.g. “Trending”).'
    )

    # ── Autopilot controls (B4) — apply to the self-optimizing reranker ──────
    exploration_rate = models.FloatField(
        null=True,
        blank=True,
        help_text='Override the bandit exploration rate (0–1). Blank = default.',
    )
    diversity_cap = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='Override the max items per category in the head. Blank = default.',
    )
    segment_override = models.CharField(
        max_length=64,
        blank=True,
        help_text='Force a bandit segment for everyone (advanced). Blank = per-visitor.',
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
        'catalog.Product', on_delete=models.CASCADE, related_name='dynamic_grid_item'
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
        return f'{self.title} (Probability: {self.purchase_probability:.2f})'


class BanditArm(models.Model):
    """Per-(product, visitor-segment) Beta-Bernoulli posterior for the self-
    optimizing "autopilot" reranker.

    The posterior is rebuilt nightly (``tasks.rebuild_bandit_posteriors``) from
    real product-view engagement bucketed by an anonymous, PII-free segment
    (device × day-part × auth): views in sessions that went on to convert score
    higher. At serve time the reranker draws one Thompson sample per arm
    (``random.betavariate(alpha, beta)`` — pure-Python, no numpy) and ranks by it,
    so well-performing products rise while uncertainty keeps exploring newcomers.

    ``alpha = 1 + reward`` and ``beta = 1 + (trials - reward)`` — a Beta(1,1)
    uniform prior for an unseen arm, so cold-start arms are naturally explored.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.CASCADE, related_name='bandit_arms'
    )
    segment = models.CharField(
        max_length=64,
        db_index=True,
        help_text='Anonymous visitor segment, e.g. "mobile:evening:anon".',
    )
    alpha = models.FloatField(default=1.0)
    beta = models.FloatField(default=1.0)
    trials = models.PositiveIntegerField(default=0)
    reward = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['product', 'segment'], name='dynbandit_product_segment')
        ]
        indexes = [models.Index(fields=['segment', 'product'], name='dynbandit_segment_idx')]

    def __str__(self) -> str:
        return f'{self.product_id} @ {self.segment} (α={self.alpha:.1f} β={self.beta:.1f})'

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)


class MerchandisingProposal(models.Model):
    """A proposed merchandising change from the nightly autopilot merchandiser —
    a **human-checkpoint review queue**.

    Nothing is applied automatically: the merchandiser reads the store's own
    signals (live blocks, bandit winners, propensity distribution, experiment
    results) and files a proposal; a staff member then Approves (which applies a
    low-risk config action — provision/enable a block, feature products) or
    Dismisses it. Approval is audited via ``core.audit``. Risky actions are out of
    scope by construction, so this needs no heavier safety gate than the human
    click. (ADR 0029: the optional LLM rationale uses the shared provider for a
    bounded text task — it does not add an agent class.)
    """

    KIND_CHOICES = [
        ('enable_autopilot', 'Turn on Autopilot'),
        ('provision_block', 'Add a merchandising block'),
        ('feature_products', 'Feature high-propensity products'),
        ('winning_strategy', 'Experiment result'),
        ('insight', 'Merchandising insight'),
    ]
    STATUS_CHOICES = [
        ('proposed', 'Proposed'),
        ('approved', 'Approved'),
        ('dismissed', 'Dismissed'),
    ]
    # Kinds that perform a config change on approval (vs informational insights).
    ACTIONABLE_KINDS = ('enable_autopilot', 'provision_block', 'feature_products')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=32, choices=KIND_CHOICES, db_index=True)
    title = models.CharField(max_length=200)
    rationale = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    # Dedup key — the merchandiser skips filing a proposal that already has an
    # open (proposed) row with the same signature.
    signature = models.CharField(max_length=200, db_index=True)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default='proposed', db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', '-created_at'], name='dynprop_status_idx')]

    def __str__(self) -> str:
        return f'{self.get_kind_display()}: {self.title} [{self.status}]'

    @property
    def is_actionable(self) -> bool:
        return self.kind in self.ACTIONABLE_KINDS
