"""
Morpheus CMS - Catalog Models
Products, Variants, Categories, Collections, Attributes, Reviews
"""

# ruff: noqa: PLC0415, SIM105, E402, I001
# - PLC0415: image_pipeline + logging imports are inline because they're
#   lazy-imported in a Product save hook to avoid a circular dependency
#   at app-load time.
# - SIM105: leaving the try/except/pass on file deletion (over
#   contextlib.suppress) for readability with two distinct exceptions.
# - E402: pre_delete signal registration belongs after the model defs
#   (it references the ProductImage class), not at module top.
# - I001: legacy import order kept for git-blame stability.
import uuid

from core.utils.html import sanitize_richtext
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils.text import slugify
from djmoney.models.fields import MoneyField
from morpheus import models
from mptt.models import MPTTModel, TreeForeignKey
from taggit.managers import TaggableManager
from taggit.models import GenericUUIDTaggedItemBase, TaggedItemBase


class Vendor(models.Model):
    """Vendor / supplier — lives in catalog to avoid circular migration deps."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='vendors/', blank=True, null=True)
    owner = models.ForeignKey(
        'customers.Customer', on_delete=models.SET_NULL, null=True, blank=True
    )
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Category(MPTTModel):
    """Hierarchical category tree (MPTT for efficient tree queries)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    parent = TreeForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children'
    )
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class MPTTMeta:
        order_insertion_by = ['sort_order', 'name']

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Collection(models.Model):
    """Curated product collections (e.g. 'Summer Sale', 'New Arrivals')."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='collections/', blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['is_active', 'is_featured']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class TagProfile(models.Model):
    """Editorial copy for a product tag.

    taggit's ``Tag`` has no description, so a tag landing page (the ``?tag=`` PLP)
    has nothing to show below its title. This side-table gives every tag an
    optional display name + attractive description, keyed by the tag's slug so
    it survives the tag being renamed/re-created. One row per tag the merchant
    wants to write copy for; tags without a row just render their bare name.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=200, unique=True, db_index=True)
    name = models.CharField(max_length=200, help_text='Display name shown as the page title.')
    description = models.TextField(blank=True, help_text='Shown below the title on the tag page.')
    meta_description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @classmethod
    def for_tag(cls, value: str):
        """Resolve the profile for a ``?tag=`` value (a tag name or slug).

        The tag filter matches by name case-insensitively while product cards
        link by slug, so normalise through slugify to hit the keyed row either
        way. Returns None when no editorial copy exists for the tag.
        """
        if not value:
            return None
        return cls.objects.filter(slug=slugify(value)).first()


class AttributeGroup(models.Model):
    """Groups attributes (e.g. 'Clothing Sizes', 'Colors')."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class Attribute(models.Model):
    """Product attribute definition (e.g. 'Size', 'Color', 'Material')."""

    INPUT_TYPES = [
        ('select', 'Select'),
        ('multiselect', 'Multi-Select'),
        ('text', 'Text'),
        ('numeric', 'Numeric'),
        ('boolean', 'Boolean'),
        ('color', 'Color Swatch'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(AttributeGroup, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    input_type = models.CharField(max_length=15, choices=INPUT_TYPES, default='select')
    is_variant = models.BooleanField(default=False, help_text='Used to create product variants')
    is_filterable = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class AttributeValue(models.Model):
    """Possible values for an attribute (e.g. 'Red', 'XL')."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE, related_name='values')
    name = models.CharField(max_length=100)
    slug = models.SlugField()
    value = models.CharField(max_length=200, blank=True)  # hex for color, etc.
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']
        unique_together = ('attribute', 'slug')

    def __str__(self):
        return f'{self.attribute.name}: {self.name}'


class UUIDTaggedItem(GenericUUIDTaggedItemBase, TaggedItemBase):
    """Taggit through-model with a UUID ``object_id``.

    ``Product`` has a ``UUIDField`` primary key, but taggit's default
    ``taggit.TaggedItem`` stores ``object_id`` as an ``IntegerField``. On
    Postgres that makes every ``tags__…`` join (and ``tags.add()``) a
    ``uuid = integer`` type error — a 500. sqlite's loose typing hides it, so
    it slipped through tests. Routing the manager through this UUID-typed
    through-model makes the join ``uuid = uuid`` and the tag filter work.
    """

    class Meta:
        verbose_name = 'Tagged item'
        verbose_name_plural = 'Tagged items'


class Product(models.Model):
    """Core product model."""

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('archived', 'Archived'),
    ]
    PRODUCT_TYPES = [
        ('simple', 'Simple'),
        ('variable', 'Variable'),
        ('digital', 'Digital'),
        ('bundle', 'Bundle'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True)
    sku = models.CharField(max_length=100, unique=True, blank=True)
    product_type = models.CharField(max_length=10, choices=PRODUCT_TYPES, default='simple')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')

    # Pricing
    price = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    compare_at_price = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='USD',
        null=True,
        blank=True,
        help_text='Original price (shown as struck-through)',
    )
    cost_price = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='USD',
        null=True,
        blank=True,
        help_text='Your cost (not shown to customers)',
    )

    # Enterprise Multi-Currency & Localization
    localized_prices = models.JSONField(
        default=dict, blank=True, help_text='{"EUR": "19.99", "JPY": "2500"}'
    )
    localized_translations = models.JSONField(
        default=dict, blank=True, help_text='{"fr": {"name": "Produit", "description": "..."}}'
    )

    # Content
    short_description = models.TextField(blank=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products'
    )
    # Multi-category — products can ALSO surface under any of these
    # category landings without losing their primary `category` FK
    # (which stays canonical for breadcrumbs, JSON-LD, and SEO).
    additional_categories = models.ManyToManyField(
        Category,
        blank=True,
        related_name='also_listed_products',
        help_text='Extra categories this product is listed under, in addition to its primary category.',
    )
    collections = models.ManyToManyField(Collection, blank=True, related_name='products')
    tags = TaggableManager(through=UUIDTaggedItem, blank=True)
    attributes = models.ManyToManyField(Attribute, blank=True, through='ProductAttribute')

    # Multi-Tenancy
    channels = models.ManyToManyField('core.StoreChannel', blank=True, related_name='products')

    # Shipping
    weight = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    weight_unit = models.CharField(max_length=5, default='kg')
    requires_shipping = models.BooleanField(default=True)

    # SEO — basic
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    focus_keyword = models.CharField(
        max_length=120,
        blank=True,
        help_text='Primary keyword this product targets — used by SEO audits.',
    )
    canonical_url = models.URLField(
        blank=True,
        help_text='Override the canonical URL. Leave blank to use the default product URL.',
    )

    # SEO — Open Graph (Facebook, LinkedIn, etc.). Falls back to meta_* / name.
    og_title = models.CharField(max_length=200, blank=True)
    og_description = models.TextField(blank=True)
    og_image = models.ImageField(upload_to='products/og/', blank=True, null=True)

    # SEO — Twitter Card.
    TWITTER_CARD_CHOICES = [
        ('summary', 'Summary'),
        ('summary_large_image', 'Summary with large image'),
    ]
    twitter_title = models.CharField(max_length=200, blank=True)
    twitter_description = models.TextField(blank=True)
    twitter_image = models.ImageField(upload_to='products/twitter/', blank=True, null=True)
    twitter_card = models.CharField(
        max_length=24,
        choices=TWITTER_CARD_CHOICES,
        default='summary_large_image',
        blank=True,
    )

    # SEO — crawler controls.
    noindex = models.BooleanField(
        default=False,
        help_text='Tell search engines to skip this page.',
    )
    nofollow = models.BooleanField(
        default=False,
        help_text='Tell search engines not to follow links from this page.',
    )

    # SEO — extra JSON-LD overrides.
    structured_data = models.JSONField(
        default=dict,
        blank=True,
        help_text='Extra fields merged into the auto-generated JSON-LD (e.g. brand, gtin, mpn).',
    )

    # Digital
    digital_file = models.FileField(upload_to='digital/', blank=True, null=True)

    # Flags
    is_featured = models.BooleanField(default=False, db_index=True)
    is_taxable = models.BooleanField(default=True)
    track_inventory = models.BooleanField(default=True)

    vendor = models.ForeignKey(
        Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name='products'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status', 'is_featured']),
            models.Index(fields=['category']),
            models.Index(fields=['vendor']),
            models.Index(fields=['-created_at']),
            # Storefront PLP + category browse + staff_picks: every
            # query filters `status='active'` first then narrows by
            # category/collection. A composite `(status, category)`
            # index is the right access path — drops the existing
            # category-only index off the hot path on stores with
            # many archived products.
            models.Index(fields=['status', 'category'], name='catalog_product_status_cat_idx'),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        # description / short_description are rendered `|safe` on the PDP —
        # sanitise on save so a compromised staff session, a GraphQL/agent
        # write, or prompt-injected LLM output can't persist stored XSS.
        self.description = sanitize_richtext(self.description)
        self.short_description = sanitize_richtext(self.short_description)
        super().save(*args, **kwargs)

    @property
    def is_on_sale(self) -> bool:
        # `compare_at_price` is nullable; must always return a real bool —
        # the GraphQL type declares this field non-nullable, so a None
        # leak (from `a and b` shortcircuit) crashes resolvers.
        if not self.compare_at_price or not self.price:
            return False
        return self.compare_at_price > self.price

    @property
    def discount_percentage(self) -> int:
        if not self.is_on_sale:
            return 0
        diff = self.compare_at_price.amount - self.price.amount
        return round((diff / self.compare_at_price.amount) * 100)

    @property
    def display_price(self):
        """Storefront-visible price.

        Variable products: the LOWEST active variant.effective_price, so
        PLP cards render "From $X" instead of the parent's $0 (which
        ProductForm.clean() auto-sets when product_type='variable').
        Simple / Digital / Bundle: just self.price.
        """
        if self.product_type == 'variable':
            cheapest = None
            for v in self.variants.filter(is_active=True):
                ep = v.effective_price
                if ep is None:
                    continue
                if cheapest is None or ep.amount < cheapest.amount:
                    cheapest = ep
            if cheapest is not None:
                return cheapest
        return self.price

    @property
    def price_starts_from(self) -> bool:
        """True when display_price reflects the minimum across 2+ active
        variants — PLP templates prefix with "From " when set.
        """
        if self.product_type != 'variable':
            return False
        return self.variants.filter(is_active=True).count() > 1

    @property
    def primary_image(self):
        return self.images.filter(is_primary=True).first() or self.images.first()

    @property
    def average_rating(self):
        reviews = self.reviews.filter(is_approved=True)
        if reviews.exists():
            return reviews.aggregate(models.Avg('rating'))['rating__avg']
        return None

    @property
    def review_count(self) -> int:
        """Approved-only count. Storefront PDP renders this next to the
        average rating; the JSON-LD aggregateRating uses it too."""
        return self.reviews.filter(is_approved=True).count()


class ProductAttribute(models.Model):
    """Assigns attribute values to a product."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)
    values = models.ManyToManyField(AttributeValue)

    class Meta:
        unique_together = ('product', 'attribute')


class ProductImage(models.Model):
    """Product images with ordering and alt text.

    On save we render a WebP variant alongside the original. The storefront
    template prefers ``webp_image.url`` when available — WebP is ~25-35%
    smaller than JPEG at equivalent quality and is supported by every modern
    browser, so this is a free LCP improvement on PDP/PLP.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    webp_image = models.ImageField(upload_to='products/webp/', blank=True, null=True)
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', '-is_primary']
        indexes = [
            # PDP fetches `product.images.all().order_by('sort_order')`
            # on every render. The FK on `product` is auto-indexed but
            # without the composite `(product, sort_order)` the planner
            # has to either sort N rows in memory or do a heap fetch
            # per row to read sort_order. Composite covers the ordered
            # fetch directly.
            models.Index(fields=['product', 'sort_order'], name='catalog_image_product_sort_idx'),
        ]

    def __str__(self):
        return f'Image for {self.product.name}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.image:
            return
        # Skip if the source is already an optimised variant or we
        # already have one cached for this filename. Avoids re-encoding
        # on every metadata save (alt_text edit, sort_order drag, …).
        src_name = (self.image.name or '').lower()
        if src_name.endswith('.webp') or src_name.endswith('.avif'):
            return
        expected_webp = f'products/webp/{src_name.rsplit("/", 1)[-1].rsplit(".", 1)[0]}.webp'
        if self.webp_image and self.webp_image.name == expected_webp:
            return
        # Variant generation respects the store-wide image defaults
        # (Settings → General → Image defaults, commit a57a4eb). The
        # configured PDP width / height is applied as a max-resize
        # (preserves aspect ratio); the configured format becomes the
        # encoded output. Falls back to WebP @ 800×1200 if the panel
        # isn't configured.
        from plugins.installed.catalog.image_pipeline import generate_pdp_variant

        try:
            generate_pdp_variant(self)
        except Exception:  # noqa: BLE001 — image upload must not fail on variant gen
            import logging

            logging.getLogger('morpheus.catalog').warning(
                'Failed to generate image variant for ProductImage %s',
                self.pk,
                exc_info=True,
            )

    def delete(self, *args, **kwargs):
        # Strip files before the row goes away. The pre_delete signal
        # registered below covers the cascade / queryset-delete paths
        # that bypass this method.
        _strip_image_files(self)
        return super().delete(*args, **kwargs)


def _strip_image_files(instance):
    """Remove the underlying media files for a ProductImage.

    Idempotent on missing files. Called from both the model's delete()
    override (explicit instance.delete()) and the pre_delete signal
    handler (cascade + queryset.delete()) so files don't leak whichever
    code path triggers the removal.
    """
    for field in (instance.image, instance.webp_image):
        if field and field.name:
            try:
                field.delete(save=False)
            except (FileNotFoundError, OSError):
                pass


from django.db.models.signals import pre_delete
from django.dispatch import receiver


@receiver(pre_delete, sender='catalog.ProductImage')
def _productimage_pre_delete(sender, instance, **kwargs):
    """Cascade/queryset.delete() bypass Model.delete() — so they leak
    files. The pre_delete signal DOES fire for every instance, even via
    cascade, so we hook the file-strip here.
    """
    _strip_image_files(instance)


class ProductVariant(models.Model):
    """
    A specific purchasable version of a product.
    e.g. Red T-Shirt / Size XL

    Shopify-parity surface (Phase 1 of docs/plans/variant-shopify-parity.md):
    every variant is independently flaggable as physical / digital /
    virtual, with its own requires_shipping, taxability, inventory
    policy, barcode, and optional digital file. Defaults preserve
    today's behaviour exactly so existing rows need no data migration.
    """

    VARIANT_TYPE_CHOICES = [
        ('physical', 'Physical — ships to a customer address'),
        ('digital', 'Digital — downloadable file'),
        ('virtual', 'Virtual — service, gift card, booking, no shipment'),
    ]
    INVENTORY_POLICY_CHOICES = [
        ('deny', 'Deny — refuse orders when out of stock'),
        ('continue', 'Continue — accept backorders'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=100, unique=True)
    price = MoneyField(
        max_digits=14, decimal_places=2, default_currency='USD', null=True, blank=True
    )
    compare_at_price = MoneyField(
        max_digits=14, decimal_places=2, default_currency='USD', null=True, blank=True
    )

    # Per-variant copy — used when a variant has its own marketing pitch
    # distinct from the parent product (e.g. "Signed hardcover" gets a
    # paragraph the paperback doesn't). Both fall back to Product's text
    # at storefront-render time when blank, so adding these is non-breaking.
    short_description = models.TextField(
        blank=True,
        help_text='One-line variant pitch. Falls back to Product.short_description when blank.',
    )
    description = models.TextField(
        blank=True,
        help_text='Full variant description. Falls back to Product.description when blank.',
    )

    # Free-text size label (e.g. "XL", "300 ml", "9.5 US"). Independent of the
    # AttributeValue M2M so merchants can ship variants without setting up the
    # full attribute system. When you DO use attributes, leave this blank and
    # use the structured attribute_values M2M below instead.
    size = models.CharField(
        max_length=50,
        blank=True,
        help_text='Quick free-text size label, e.g. "XL" or "300 ml". For structured size pickers, use attribute_values.',
    )

    localized_prices = models.JSONField(
        default=dict, blank=True, help_text='{"EUR": "19.99", "JPY": "2500"}'
    )

    cost_price = MoneyField(
        max_digits=14, decimal_places=2, default_currency='USD', null=True, blank=True
    )
    attribute_values = models.ManyToManyField(AttributeValue, blank=True)
    image = models.ForeignKey(ProductImage, on_delete=models.SET_NULL, null=True, blank=True)
    weight = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)

    # ── Shopify parity — per-variant fulfillment + tax + inventory ─────
    variant_type = models.CharField(
        max_length=10,
        choices=VARIANT_TYPE_CHOICES,
        default='physical',
        help_text='Physical (ships), digital (downloadable), or virtual (no fulfillment).',
    )
    requires_shipping = models.BooleanField(
        default=True,
        help_text='When false, checkout skips the shipping address step. Auto-flipped to false for digital/virtual variants in the dashboard form.',
    )
    is_taxable = models.BooleanField(
        default=True,
        help_text='Per-variant override of Product.is_taxable. Useful for EU VAT where digital + physical have different rules.',
    )
    inventory_policy = models.CharField(
        max_length=10,
        choices=INVENTORY_POLICY_CHOICES,
        default='deny',
        help_text='What happens when stock hits zero. Continue allows backorders.',
    )
    barcode = models.CharField(
        max_length=50,
        blank=True,
        help_text='UPC / EAN / ISBN. Used by POS, wholesale, and inventory sync.',
    )
    digital_file = models.FileField(
        upload_to='digital/variants/',
        blank=True,
        null=True,
        help_text='Per-variant override of Product.digital_file. Use when a single product sells in multiple digital formats (PDF / EPUB / MOBI).',
    )

    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order']

    def __str__(self):
        return f'{self.product.name} - {self.name}'

    @property
    def effective_price(self):
        return self.price or self.product.price


class Review(models.Model):
    """Customer product review with rating."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey(
        'customers.Customer', on_delete=models.CASCADE, related_name='reviews'
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    is_approved = models.BooleanField(default=False)
    is_verified_purchase = models.BooleanField(default=False)
    helpful_votes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'customer')
        ordering = ['-created_at']
        indexes = [
            # PDP "Reader letters" block + generate_pdp_faqs:
            # Review.objects.filter(product=X, is_approved=True)
            #   .order_by('-helpful_votes', '-created_at')
            # Without this index the planner does a seq scan filtered
            # by product (auto-indexed FK) and then in-memory sort by
            # helpful_votes. At <1000 reviews per product it's cheap,
            # but the index is small + cheap and the query is hot.
            models.Index(
                fields=['product', 'is_approved', '-helpful_votes'],
                name='catalog_review_pdp_idx',
            ),
        ]

    def __str__(self):
        return f'{self.rating}★ review by {self.customer.email} on {self.product.name}'


class PriceSchedule(models.Model):
    """A planned price change for a product/variant.

    A celery beat task scans for entries with `applied_at__isnull=True` and
    `effective_at <= now`, then writes the new price + marks them applied.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_schedules')
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='price_schedules',
    )
    new_price = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    new_compare_at = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='USD',
        null=True,
        blank=True,
    )
    effective_at = models.DateTimeField(db_index=True)
    applied_at = models.DateTimeField(null=True, blank=True, db_index=True)
    note = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['effective_at']
        indexes = [
            models.Index(fields=['effective_at', 'applied_at']),
        ]
