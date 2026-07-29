import uuid

from django.conf import settings
from djmoney.models.fields import MoneyField

from morpheus.plugin import models


class AgentIntent(models.Model):
    """
    Lifecycle record for a single agent action against the platform.

    The intent state machine is:

        proposed  -> authorized -> executing -> completed
                                              -> failed
                  -> rejected
                  -> expired

    Every state change is recorded in `AgentIntentEvent` and emitted on the
    Morpheus event bus, so analytics, fraud, and budget consumers can react
    without coupling to the AI plugin.
    """

    KIND_CHOICES = [
        ('browse', 'Browse'),
        ('compare', 'Compare'),
        ('checkout', 'Checkout'),
        ('return', 'Return'),
        ('subscribe', 'Subscribe'),
        ('cancel', 'Cancel'),
        ('chat', 'Chat'),
        ('custom', 'Custom'),
    ]
    STATE_CHOICES = [
        ('proposed', 'Proposed'),
        ('authorized', 'Authorized'),
        ('executing', 'Executing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(
        'AgentRegistration',
        on_delete=models.CASCADE,
        related_name='intents',
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agent_intents',
    )
    channel = models.ForeignKey(
        'core.StoreChannel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    kind = models.CharField(max_length=15, choices=KIND_CHOICES, db_index=True)
    state = models.CharField(
        max_length=12,
        choices=STATE_CHOICES,
        default='proposed',
        db_index=True,
    )
    summary = models.CharField(
        max_length=300,
        blank=True,
        help_text='Human-readable summary, e.g. "Buy a 32oz blender under $80"',
    )
    payload = models.JSONField(
        default=dict,
        help_text='Structured intent inputs: target product ids, filters, address etc.',
    )
    result = models.JSONField(
        default=dict,
        help_text='Execution outcome: order id, refund id, cart id, errors.',
    )
    estimated_cost = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='USD',
        null=True,
        blank=True,
    )
    actual_cost = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='USD',
        null=True,
        blank=True,
    )
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    receipt_signature = models.CharField(
        max_length=128,
        blank=True,
        help_text='HMAC over the canonical receipt payload, signed by the agent secret.',
    )
    receipt_signed_at = models.DateTimeField(null=True, blank=True)
    correlation_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text='Caller-supplied id for tracing across systems.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['agent', '-created_at']),
            models.Index(fields=['agent', 'state']),
            models.Index(fields=['customer', '-created_at']),
        ]

    def __str__(self) -> str:
        return f'AgentIntent({self.kind}/{self.state}) by {self.agent_id}'


class AgentIntentEvent(models.Model):
    """Immutable audit log of every state transition on an AgentIntent."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    intent = models.ForeignKey(
        AgentIntent,
        on_delete=models.CASCADE,
        related_name='events',
    )
    from_state = models.CharField(max_length=12, blank=True)
    to_state = models.CharField(max_length=12)
    actor = models.CharField(
        max_length=20,
        choices=[
            ('agent', 'Agent'),
            ('customer', 'Customer'),
            ('merchant', 'Merchant'),
            ('system', 'System'),
        ],
        default='system',
    )
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['intent', 'created_at']),
        ]


class AgentMemory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='ai_memories',
    )
    agent_id = models.CharField(max_length=200, blank=True)
    memory_type = models.CharField(
        max_length=15,
        choices=[
            ('preference', 'Preference'),
            ('constraint', 'Constraint'),
            ('context', 'Life Context'),
            ('relationship', 'Relationship'),
            ('feedback', 'Feedback'),
            ('behavior', 'Observed Behavior'),
        ],
    )
    key = models.CharField(max_length=200)
    value = models.JSONField()
    confidence = models.FloatField(default=1.0)
    source = models.CharField(
        max_length=10,
        choices=[
            ('explicit', 'Customer Stated'),
            ('inferred', 'Inferred from Behavior'),
            ('agent', 'Set by AI Agent'),
            ('purchase', 'Derived from Purchase'),
        ],
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-confidence', '-updated_at']
        indexes = [
            models.Index(fields=['customer', 'memory_type']),
            models.Index(fields=['agent_id']),
        ]


class AgentRegistration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent_id = models.CharField(max_length=200, unique=True)
    owner_email = models.EmailField()
    owner_customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    token = models.CharField(max_length=500, unique=True)
    signing_secret = models.CharField(
        max_length=128,
        blank=True,
        help_text='HMAC secret used to sign agent receipts. Auto-generated.',
    )
    token_expires_at = models.DateTimeField(null=True, blank=True)
    can_browse = models.BooleanField(default=True)
    can_purchase = models.BooleanField(default=False)
    can_manage_inventory = models.BooleanField(default=False)
    budget_limit_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    budget_limit_currency = models.CharField(max_length=3, default='USD')
    allowed_categories = models.JSONField(default=list)
    purchase_requires_approval = models.BooleanField(default=True)
    total_spend_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_active_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.signing_secret:
            import secrets as _secrets

            self.signing_secret = _secrets.token_urlsafe(48)
        super().save(*args, **kwargs)

    def remaining_budget(self):
        """Decimal remaining budget, or None when no cap is configured."""
        if self.budget_limit_amount is None:
            return None
        return self.budget_limit_amount - (self.total_spend_amount or 0)

    def can_afford(self, amount) -> bool:
        """Return True iff the configured budget can absorb `amount`."""
        if self.budget_limit_amount is None:
            return True
        from decimal import Decimal

        return Decimal(amount) <= (self.budget_limit_amount - (self.total_spend_amount or 0))


class PromptTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    prompt_type = models.CharField(
        max_length=30,
        choices=[
            ('product_description', 'Product Description Generator'),
            ('intent_parser', 'Intent Parser'),
            ('semantic_search', 'Semantic Search Rewriter'),
            ('cart_recovery', 'Cart Recovery Message'),
            ('zero_shot_catalog', 'Zero-Shot Catalog'),
            ('recommendation', 'Recommendation Explanation'),
            ('merchant_insight', 'Merchant Insight Generator'),
            ('chat_response', 'Customer Chat Response'),
            ('dynamic_pricing', 'Dynamic Pricing Reasoning'),
        ],
    )
    version = models.PositiveIntegerField(default=1)
    template = models.TextField(help_text='Jinja2 template with {{variables}}')
    system_message = models.TextField(blank=True)
    model_override = models.CharField(max_length=100, blank=True)
    temperature = models.FloatField(default=0.7)
    max_tokens = models.PositiveIntegerField(default=1000)
    is_active = models.BooleanField(default=True)
    performance_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', '-version']
        unique_together = ('name', 'version')


class AIExperiment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    prompt_a = models.ForeignKey(
        PromptTemplate, on_delete=models.CASCADE, related_name='experiments_a'
    )
    prompt_b = models.ForeignKey(
        PromptTemplate, on_delete=models.CASCADE, related_name='experiments_b'
    )
    metric = models.CharField(
        max_length=25,
        choices=[
            ('conversion_rate', 'Conversion Rate'),
            ('click_through', 'Click-Through Rate'),
            ('cart_add', 'Add-to-Cart Rate'),
            ('revenue_per_session', 'Revenue Per Session'),
            ('chat_satisfaction', 'Chat Satisfaction Score'),
        ],
    )
    traffic_split = models.FloatField(default=0.5)
    status = models.CharField(
        max_length=10,
        choices=[('running', 'Running'), ('concluded', 'Concluded'), ('paused', 'Paused')],
        default='running',
    )
    winner = models.ForeignKey(
        PromptTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_experiments',
    )
    started_at = models.DateTimeField(auto_now_add=True)
    concluded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']


class AIInteraction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interaction_type = models.CharField(
        max_length=30,
        choices=[
            ('completion', 'Text Completion'),
            ('embedding', 'Embedding'),
            ('intent_parse', 'Intent Parsing'),
            ('product_description', 'Product Description'),
            ('recommendation', 'Recommendation'),
            ('chat', 'Customer Chat'),
            ('zero_shot', 'Zero-Shot Catalog'),
            ('merchant_insight', 'Merchant Insight'),
            ('dynamic_pricing', 'Dynamic Pricing'),
            ('synthetic_test', 'Synthetic Test'),
        ],
    )
    model_used = models.CharField(max_length=100)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    input_data = models.JSONField(default=dict)
    output_data = models.JSONField(default=dict)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    agent_id = models.CharField(max_length=200, blank=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    product = models.ForeignKey('catalog.Product', on_delete=models.SET_NULL, null=True, blank=True)
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True)
    prompt_template = models.ForeignKey(
        PromptTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['interaction_type', 'created_at']),
            models.Index(fields=['customer', 'created_at']),
        ]


class DemandForecast(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product_variant = models.ForeignKey(
        'catalog.ProductVariant', on_delete=models.CASCADE, related_name='demand_forecasts'
    )
    forecast_date = models.DateField()
    predicted_units = models.IntegerField()
    confidence_low = models.IntegerField()
    confidence_high = models.IntegerField()
    model_version = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['forecast_date']
        unique_together = ('product_variant', 'forecast_date', 'model_version')


class MerchantInsight(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    insight_type = models.CharField(
        max_length=15,
        choices=[
            ('opportunity', 'Revenue Opportunity'),
            ('risk', 'Risk / Alert'),
            ('action', 'Suggested Action'),
            ('report', 'Automated Report'),
        ],
    )
    priority = models.CharField(
        max_length=10,
        choices=[
            ('critical', 'Critical'),
            ('high', 'High'),
            ('medium', 'Medium'),
            ('low', 'Low'),
        ],
        default='medium',
    )
    title = models.CharField(max_length=200)
    body = models.TextField()
    suggested_action = models.JSONField(default=dict)
    estimated_impact = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    is_approved = models.BooleanField(null=True)
    ai_executed = models.BooleanField(default=False)
    execution_result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    acted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']


class ProductEmbedding(models.Model):
    """
    Vector embedding for a product's description + key attributes.

    Stored as a JSON list of floats so it works on every supported backend.
    On Postgres-with-pgvector deployments a future migration will swap this
    for a `pgvector.django.VectorField` and a HNSW index — the surrounding
    service code already runs over JSON, so the swap is transparent.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.OneToOneField(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='embedding',
    )
    vector = models.JSONField(default=list)
    dim = models.PositiveIntegerField(default=0)
    model = models.CharField(max_length=100, blank=True)
    source_text_hash = models.CharField(max_length=64, blank=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']


class KnowledgeChunk(models.Model):
    """A chunk of unstructured knowledge for Linda's RAG index.

    One row per heading-sized slice of a source document (platform docs, ADRs,
    release notes, product long-copy, or any plugin-contributed source via the
    KNOWLEDGE_SOURCES filter). ``vector`` is a JSON list of floats — same shape
    as ``ProductEmbedding``; a future pgvector migration swaps it for a
    VectorField + HNSW index (Phase 2, see docs/plans/rag-knowledge-base.md).
    ``(source, ref)`` identifies the chunk for idempotent upserts.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=64, db_index=True)
    ref = models.CharField(max_length=200)
    title = models.CharField(max_length=300, blank=True)
    text = models.TextField()
    vector = models.JSONField(default=list)
    dim = models.PositiveIntegerField(default=0)
    source_text_hash = models.CharField(max_length=64, blank=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['source', 'ref']
        constraints = [
            models.UniqueConstraint(fields=['source', 'ref'], name='uniq_knowledge_source_ref')
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f'{self.source}:{self.ref}'


class DynamicPriceRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.OneToOneField(
        'catalog.Product', on_delete=models.CASCADE, related_name='dynamic_price_rule'
    )
    multiplier = models.DecimalField(max_digits=5, decimal_places=4, default=1.0000)
    reasoning = models.TextField(blank=True)
    last_evaluated_at = models.DateTimeField(auto_now=True)
