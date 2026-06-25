"""
Core models — StoreSettings only.
Vendor moved to catalog plugin to avoid circular migration dependency.
"""

import uuid

from django.db import models


class StoreSettings(models.Model):
    """Global store configuration singleton."""

    store_name = models.CharField(max_length=200, default='Morpheus Store')
    store_description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='store/', blank=True, null=True)
    favicon = models.ImageField(upload_to='store/', blank=True, null=True)
    product_placeholder_image = models.ImageField(
        upload_to='store/',
        blank=True,
        null=True,
        help_text='Fallback cover shown on the storefront when a product has no image of its own.',
    )
    primary_currency = models.CharField(max_length=3, default='USD')
    country = models.CharField(max_length=2, default='US')
    timezone = models.CharField(max_length=50, default='UTC')
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    ai_provider = models.CharField(max_length=20, default='openai')
    contact_email = models.EmailField(blank=True)
    support_phone = models.CharField(max_length=30, blank=True)
    social_links = models.JSONField(default=dict)
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    
    # Advanced UX Settings
    guided_ux_mode = models.BooleanField(
        default=True, 
        help_text='Enable enhanced micro-animations and highly visible contextual explanations across the dashboard.'
    )

    # Custom SMTP Overrides
    smtp_host = models.CharField(max_length=200, blank=True, help_text='e.g. smtp.resend.com')
    smtp_port = models.IntegerField(default=587)
    smtp_user = models.CharField(max_length=200, blank=True)
    smtp_password = models.CharField(max_length=200, blank=True)
    default_from_email = models.CharField(
        max_length=200, blank=True, help_text='e.g. noreply@dotbooks.shop'
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Store Settings'
        verbose_name_plural = 'Store Settings'

    def __str__(self):
        return self.store_name

    @classmethod
    def get(cls, key: str, default=None):
        from django.db import DatabaseError

        try:
            obj = cls.objects.first()
        except DatabaseError:
            # DB unavailable (e.g. migrations not yet applied) — degrade gracefully.
            return default
        return getattr(obj, key, default) if obj else default


class StoreChannel(models.Model):
    """
    A storefront channel. One Morpheus backend serves N channels — different
    domains, currencies, default countries, allowed payment methods, and
    per-channel product pricing/availability via `ProductChannelListing`.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=80, unique=True, db_index=True, default='default')
    name = models.CharField(max_length=100)
    domain = models.CharField(max_length=200, unique=True)
    currency = models.CharField(
        max_length=3, default='USD', help_text='ISO 4217 currency code; prices use this.'
    )
    default_country = models.CharField(
        max_length=2, default='US', help_text='ISO 3166-1 alpha-2; used for tax/shipping defaults.'
    )
    country_codes = models.JSONField(
        default=list,
        blank=True,
        help_text='Optional list of ISO countries this channel serves (empty = global).',
    )
    is_default = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_default', 'name']

    def __str__(self):
        return f'{self.name} ({self.domain} · {self.currency})'

    @classmethod
    def resolve_for_request(cls, request) -> 'StoreChannel | None':
        """Pick the best channel for `request` — by host, else default, else first."""
        if request is None:
            return cls.objects.filter(is_default=True).first() or cls.objects.first()
        host = (request.get_host() if hasattr(request, 'get_host') else '').split(':')[0]
        if host:
            row = cls.objects.filter(domain=host, is_active=True).first()
            if row:
                return row
        return cls.objects.filter(is_default=True).first() or cls.objects.first()


class ProductChannelListing(models.Model):
    """Per-channel pricing + visibility for a Product.

    Falls back to `Product.price` when no listing exists for that channel.
    Generic FK so we don't introduce a hard dep from core onto catalog.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.ForeignKey(
        StoreChannel, on_delete=models.CASCADE, related_name='product_listings'
    )
    # We don't import catalog.Product here — keep core decoupled.
    product_ct = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.CASCADE,
        limit_choices_to={'app_label': 'catalog', 'model': 'product'},
    )
    product_id = models.CharField(max_length=64, db_index=True)
    # MoneyField from djmoney would mean importing here; keep numeric for now.
    price_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    cost_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    is_published = models.BooleanField(default=True, db_index=True)
    visible_in_listings = models.BooleanField(default=True)
    available_for_purchase = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('channel', 'product_ct', 'product_id')
        indexes = [
            models.Index(fields=['channel', 'is_published']),
            models.Index(fields=['product_ct', 'product_id']),
        ]

    def __str__(self) -> str:
        return f'{self.channel.slug}/{self.product_id} {self.price_amount}'


def hash_api_key(raw: str) -> str:
    """SHA-256 of an API token, for hash-at-rest storage + constant lookup.
    API tokens are high-entropy random strings, so a fast cryptographic hash is
    sufficient (unlike low-entropy passwords, which need bcrypt/argon2)."""
    import hashlib

    return hashlib.sha256((raw or '').encode()).hexdigest()


class APIKey(models.Model):
    """
    Law 2: Secure Core. Granular RBAC for headless clients and Remote Plugins.

    The token is stored HASHED (``key_hash``), never in plaintext — a DB dump
    can't leak live credentials. The raw token is shown once at creation (via
    the transient ``_raw_key``) and authenticated by hash.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    # Legacy plaintext column — blanked once hashed; kept for the backfill only.
    key = models.CharField(max_length=64, blank=True, default='', editable=False)
    key_hash = models.CharField(max_length=64, db_index=True, default='', editable=False)
    key_prefix = models.CharField(
        max_length=16, default='', editable=False, help_text='First chars, for identification.'
    )
    scopes = models.JSONField(
        default=list, help_text="List of permitted scopes, e.g. ['read:products', 'write:orders']"
    )
    channel = models.ForeignKey(
        StoreChannel, on_delete=models.CASCADE, null=True, blank=True, related_name='api_keys'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'API Key: {self.name}'

    def has_scope(self, scope: str) -> bool:
        return 'admin' in self.scopes or scope in self.scopes

    def save(self, *args, **kwargs):  # noqa: DJ012
        if not self.key_hash:
            import secrets

            raw = self.key or secrets.token_urlsafe(48)
            self.key_hash = hash_api_key(raw)
            self.key_prefix = raw[:12]
            self._raw_key = raw  # transient — surfaced once at creation
            self.key = ''  # never persist the full plaintext
        super().save(*args, **kwargs)


class WebhookEndpoint(models.Model):
    """
    Subscribes external services (Remote Plugins) to Morpheus Events.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    url = models.URLField(help_text='The destination URL to POST event payloads')
    secret = models.CharField(
        max_length=255, blank=True, help_text='Used for HMAC signature verification'
    )
    events = models.JSONField(
        default=list, help_text="List of event strings to subscribe to, e.g. ['order.placed']"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.name} ({self.url})'


class OutboxEvent(models.Model):
    """
    Implements the Transactional Outbox pattern.
    Events are written here in the same DB transaction as domain mutations.
    A separate worker reads these and publishes to NATS/Kafka.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=255, db_index=True)
    payload = models.JSONField()
    status = models.CharField(
        max_length=20,
        default='PENDING',
        choices=[('PENDING', 'Pending'), ('PUBLISHED', 'Published'), ('FAILED', 'Failed')],
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)  # noqa: DJ001

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.event_type} - {self.status}'


class ExchangeRate(models.Model):
    """A snapshot rate from `base` → `quote` currency (e.g. USD → EUR).

    Used by storefront context processor to display prices in the
    visitor's chosen currency. Rates are merchant-managed (or pulled by
    a daily celery task — see plugins.installed.environments).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    base_currency = models.CharField(max_length=3, db_index=True)
    quote_currency = models.CharField(max_length=3, db_index=True)
    rate = models.DecimalField(max_digits=18, decimal_places=8)
    source = models.CharField(max_length=50, default='manual')
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('base_currency', 'quote_currency')
        indexes = [
            models.Index(fields=['base_currency', 'quote_currency']),
        ]

    def __str__(self) -> str:
        return f'{self.base_currency}→{self.quote_currency}: {self.rate}'
