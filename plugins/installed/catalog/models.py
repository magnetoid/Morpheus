"""
Morpheus CMS - Catalog Models
Products, Variants, Categories, Collections, Attributes, Reviews
"""
import uuid
from morpheus import models
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from mptt.models import MPTTModel, TreeForeignKey
from taggit.managers import TaggableManager
from djmoney.models.fields import MoneyField


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
        return f"{self.attribute.name}: {self.name}"


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
        max_digits=14, decimal_places=2, default_currency='USD',
        null=True, blank=True, help_text='Original price (shown as struck-through)'
    )
    cost_price = MoneyField(
        max_digits=14, decimal_places=2, default_currency='USD',
        null=True, blank=True, help_text='Your cost (not shown to customers)'
    )

    # Enterprise Multi-Currency & Localization
    localized_prices = models.JSONField(default=dict, blank=True, help_text='{"EUR": "19.99", "JPY": "2500"}')
    localized_translations = models.JSONField(default=dict, blank=True, help_text='{"fr": {"name": "Produit", "description": "..."}}')

    # Content
    short_description = models.TextField(blank=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products'
    )
    collections = models.ManyToManyField(Collection, blank=True, related_name='products')
    tags = TaggableManager(blank=True)
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
        max_length=120, blank=True,
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
        max_length=24, choices=TWITTER_CARD_CHOICES, default='summary_large_image', blank=True,
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
        default=dict, blank=True,
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
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
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
    def primary_image(self):
        return self.images.filter(is_primary=True).first() or self.images.first()

    @property
    def average_rating(self):
        reviews = self.reviews.filter(is_approved=True)
        if reviews.exists():
            return reviews.aggregate(models.Avg('rating'))['rating__avg']
        return None


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

    def __str__(self):
        return f"Image for {self.product.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.image:
            return
        # Skip if the source is already WebP, or we already have a variant
        # for this filename (cheap heuristic — avoids re-encoding on every save).
        src_name = (self.image.name or '').lower()
        if src_name.endswith('.webp'):
            return
        expected_webp = f'products/webp/{src_name.rsplit("/", 1)[-1].rsplit(".", 1)[0]}.webp'
        if self.webp_image and self.webp_image.name == expected_webp:
            return
        try:
            from io import BytesIO
            from django.core.files.base import ContentFile
            from PIL import Image as PILImage

            self.image.open('rb')
            try:
                pil = PILImage.open(self.image)
                pil.load()
            finally:
                self.image.close()
            if pil.mode in ('P', 'CMYK'):
                pil = pil.convert('RGB')
            elif pil.mode == 'RGBA':
                # Keep alpha — WebP handles it.
                pass
            buf = BytesIO()
            pil.save(buf, format='WEBP', quality=82, method=4)
            buf.seek(0)
            base = src_name.rsplit('/', 1)[-1].rsplit('.', 1)[0]
            self.webp_image.save(f'{base}.webp', ContentFile(buf.read()), save=False)
            super().save(update_fields=['webp_image'])
        except Exception:  # noqa: BLE001 — image upload must not fail because of WebP
            import logging
            logging.getLogger('morpheus.catalog').warning(
                'Failed to generate WebP for ProductImage %s', self.pk, exc_info=True,
            )

    def delete(self, *args, **kwargs):
        # Django's default delete removes the DB row but leaves the
        # underlying file in MEDIA_ROOT — that's a slow file-system leak
        # whenever the admin replaces a cover image. Strip the file (and
        # its WebP sibling) first; ignore missing-file errors so the
        # delete is idempotent across re-uploads + restored backups.
        for field in (self.image, self.webp_image):
            if field and field.name:
                try:
                    field.delete(save=False)
                except (FileNotFoundError, OSError):
                    pass
        return super().delete(*args, **kwargs)


class ProductVariant(models.Model):
    """
    A specific purchasable version of a product.
    e.g. Red T-Shirt / Size XL
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=100, unique=True)
    price = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', null=True, blank=True)
    compare_at_price = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', null=True, blank=True)
    
    localized_prices = models.JSONField(default=dict, blank=True, help_text='{"EUR": "19.99", "JPY": "2500"}')
    
    cost_price = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', null=True, blank=True)
    attribute_values = models.ManyToManyField(AttributeValue, blank=True)
    image = models.ForeignKey(ProductImage, on_delete=models.SET_NULL, null=True, blank=True)
    weight = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.product.name} - {self.name}"

    @property
    def effective_price(self):
        return self.price or self.product.price


class Review(models.Model):
    """Customer product review with rating."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='reviews')
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

    def __str__(self):
        return f"{self.rating}★ review by {self.customer.email} on {self.product.name}"


class PriceSchedule(models.Model):
    """A planned price change for a product/variant.

    A celery beat task scans for entries with `applied_at__isnull=True` and
    `effective_at <= now`, then writes the new price + marks them applied.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_schedules')
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE,
        null=True, blank=True, related_name='price_schedules',
    )
    new_price = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    new_compare_at = MoneyField(
        max_digits=14, decimal_places=2, default_currency='USD',
        null=True, blank=True,
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
