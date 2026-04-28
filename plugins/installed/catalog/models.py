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

    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)

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
    def is_on_sale(self):
        return self.compare_at_price and self.compare_at_price > self.price

    @property
    def discount_percentage(self):
        if self.is_on_sale:
            diff = self.compare_at_price.amount - self.price.amount
            return round((diff / self.compare_at_price.amount) * 100)
        return 0

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
    """Product images with ordering and alt text."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', '-is_primary']

    def __str__(self):
        return f"Image for {self.product.name}"


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
