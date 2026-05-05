"""
CRM models — leads, accounts, pipelines, deals, interactions, tasks, notes.

Design decisions:

* `Lead` is a contact who has not yet bought. When a lead converts (places
  their first order), we link to the existing `Customer` row instead of
  duplicating their data.
* `Account` is a B2B company. A `Customer` may belong to one account; an
  account may have many customers (employees / buyers).
* `Pipeline` + `PipelineStage` are merchant-configurable so multiple sales
  motions can coexist (e.g. retail upsell vs B2B procurement).
* `Interaction` is the universal log row — every call, email, meeting,
  note, system event lands here. Generic FK to subject lets us attach to
  any of {Lead, Customer, Account, Deal}.
* `CrmTask` is a follow-up reminder — distinct from `Interaction` because
  it's forward-looking (something to do) rather than backward-looking
  (something that happened).
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from morpheus import models
from djmoney.models.fields import MoneyField


class Lead(models.Model):
    """A pre-customer contact captured from forms, imports, or the agent layer."""

    STATUS_CHOICES = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('qualified', 'Qualified'),
        ('converted', 'Converted'),
        ('lost', 'Lost'),
    ]
    SOURCE_CHOICES = [
        ('storefront', 'Storefront form'),
        ('newsletter', 'Newsletter signup'),
        ('import', 'Import'),
        ('referral', 'Referral'),
        ('agent', 'Agent-captured'),
        ('manual', 'Manual entry'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    company = models.CharField(max_length=200, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='other')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='new', db_index=True)
    score = models.PositiveSmallIntegerField(default=0, help_text='0–100 lead score (higher = hotter).')

    converted_customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='source_lead',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='owned_leads',
    )

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    converted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['owner', 'status']),
        ]

    def __str__(self) -> str:
        return f'Lead({self.email}, {self.status})'

    @property
    def display_name(self) -> str:
        full = f'{self.first_name} {self.last_name}'.strip()
        return full or self.email


class Account(models.Model):
    """A B2B company. Optional — only used when `enable_b2b` is on."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, db_index=True)
    domain = models.CharField(max_length=200, blank=True, db_index=True)
    industry = models.CharField(max_length=120, blank=True)
    annual_revenue = MoneyField(
        max_digits=14, decimal_places=2, default_currency='USD', null=True, blank=True,
    )
    employee_count = models.PositiveIntegerField(null=True, blank=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='owned_accounts',
    )
    customers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='crm_accounts',
    )

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Pipeline(models.Model):
    """A configurable sales pipeline (set of stages)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    is_default = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_default', 'name']

    def __str__(self) -> str:
        return self.name


class PipelineStage(models.Model):
    """An ordered stage within a pipeline."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name='stages')
    name = models.CharField(max_length=80)
    order = models.PositiveSmallIntegerField(default=0)
    win_probability = models.FloatField(default=0.0, help_text='0.0–1.0; used for forecasting.')
    is_won = models.BooleanField(default=False)
    is_lost = models.BooleanField(default=False)

    class Meta:
        ordering = ['pipeline', 'order']
        unique_together = ('pipeline', 'name')

    def __str__(self) -> str:
        return f'{self.pipeline.name}/{self.name}'


class Deal(models.Model):
    """An opportunity — typically B2B, but works for retail enterprise sales too."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    pipeline = models.ForeignKey(Pipeline, on_delete=models.PROTECT, related_name='deals')
    stage = models.ForeignKey(PipelineStage, on_delete=models.PROTECT, related_name='deals')
    account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='deals',
    )
    primary_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='primary_deals',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='owned_deals',
    )
    value = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    expected_close_date = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['pipeline', 'stage']),
            models.Index(fields=['owner', '-created_at']),
            models.Index(fields=['account', '-created_at']),
        ]

    def __str__(self) -> str:
        return self.name


class Interaction(models.Model):
    """An event in the relationship history — call, email, note, system log, etc."""

    KIND_CHOICES = [
        ('note', 'Note'),
        ('call', 'Call'),
        ('email', 'Email'),
        ('meeting', 'Meeting'),
        ('sms', 'SMS'),
        ('system', 'System event'),
        ('order', 'Order activity'),
        ('agent', 'Agent activity'),
    ]
    DIRECTION_CHOICES = [
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound'),
        ('internal', 'Internal'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Generic subject — can attach to Lead, Customer, Account, or Deal.
    subject_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    subject_id = models.CharField(max_length=64)
    subject = GenericForeignKey('subject_type', 'subject_id')

    kind = models.CharField(max_length=15, choices=KIND_CHOICES, default='note', db_index=True)
    direction = models.CharField(
        max_length=10, choices=DIRECTION_CHOICES, default='internal',
    )
    summary = models.CharField(max_length=240, blank=True)
    body = models.TextField(blank=True)

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='crm_interactions',
        help_text='Who logged this — None for system / agent events.',
    )
    actor_name = models.CharField(
        max_length=120, blank=True,
        help_text='Free-text actor when not a Customer (e.g. "Concierge agent").',
    )

    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['subject_type', 'subject_id', '-occurred_at']),
            models.Index(fields=['kind', '-occurred_at']),
        ]


class CrmTask(models.Model):
    """A follow-up reminder. Forward-looking (TODO) vs Interaction (DONE)."""

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    due_at = models.DateTimeField(db_index=True)

    # Generic subject — same shape as Interaction.
    subject_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True,
    )
    subject_id = models.CharField(max_length=64, blank=True)
    subject = GenericForeignKey('subject_type', 'subject_id')

    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_crm_tasks',
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='completed_crm_tasks',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_at', '-priority']
        indexes = [
            models.Index(fields=['assignee', 'completed_at']),
            models.Index(fields=['due_at', 'completed_at']),
        ]

    @property
    def is_open(self) -> bool:
        return self.completed_at is None

    @property
    def is_overdue(self) -> bool:
        from django.utils import timezone
        return self.is_open and self.due_at < timezone.now()


class MailAccount(models.Model):
    """An IMAP/SMTP mailbox the merchant connects so support email lands in
    the CRM inbox.

    Passwords are stored as-is in this column; production deploys must keep
    the database encrypted at rest (Postgres TDE / disk encryption / managed
    secret manager). Keeping this simple deliberately — a fancier encrypted
    field can land later without changing the call sites.
    """

    PROVIDER_CHOICES = [
        ('imap', 'IMAP / SMTP (generic)'),
        ('gmail', 'Gmail (IMAP)'),
        ('outlook', 'Outlook / Office 365 (IMAP)'),
        ('fastmail', 'Fastmail (IMAP)'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    label = models.CharField(max_length=120, help_text='How merchants refer to this mailbox.')
    email_address = models.EmailField(
        unique=True, help_text='The full address — used as the From header on outbound mail.',
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='imap')

    imap_host = models.CharField(max_length=255)
    imap_port = models.PositiveIntegerField(default=993)
    imap_use_ssl = models.BooleanField(default=True)
    imap_username = models.CharField(max_length=255)
    imap_password = models.CharField(max_length=255)
    imap_folder = models.CharField(max_length=80, default='INBOX')

    smtp_host = models.CharField(max_length=255)
    smtp_port = models.PositiveIntegerField(default=465)
    smtp_use_ssl = models.BooleanField(default=True)
    smtp_use_tls = models.BooleanField(default=False)
    smtp_username = models.CharField(max_length=255)
    smtp_password = models.CharField(max_length=255)

    is_active = models.BooleanField(default=True)
    last_polled_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    # Highest IMAP UID we've already imported per account. Polling resumes
    # from `last_uid + 1` so we never reprocess the same message.
    last_uid = models.PositiveBigIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['label']

    def __str__(self):
        return f'{self.label} <{self.email_address}>'


class MailMessage(models.Model):
    """A single email — inbound (fetched via IMAP) or outbound (sent via SMTP).

    `customer` is set when the message's From/To matches a Customer email,
    so the CRM contact view can show their full mail history alongside
    interactions, deals, and tasks.
    """

    DIRECTION_CHOICES = [('in', 'Received'), ('out', 'Sent')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(MailAccount, on_delete=models.CASCADE, related_name='messages')
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES, db_index=True)

    message_id = models.CharField(
        max_length=255, blank=True, db_index=True,
        help_text='RFC822 Message-ID — used to dedupe inbound messages.',
    )
    in_reply_to = models.CharField(max_length=255, blank=True, db_index=True)
    thread_key = models.CharField(
        max_length=255, blank=True, db_index=True,
        help_text='Normalised subject + counterparty — groups a thread.',
    )

    from_address = models.CharField(max_length=320, db_index=True)
    to_addresses = models.TextField(blank=True, help_text='Comma-separated.')
    cc_addresses = models.TextField(blank=True)
    subject = models.CharField(max_length=500, blank=True)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='crm_mail_messages',
    )

    is_read = models.BooleanField(default=False, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True, db_index=True)
    received_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at', '-sent_at', '-created_at']
        indexes = [
            models.Index(fields=['account', '-received_at']),
            models.Index(fields=['customer', '-received_at']),
        ]

    def __str__(self):
        return f'[{self.get_direction_display()}] {self.subject or "(no subject)"}'

    @property
    def occurred_at(self):
        return self.received_at or self.sent_at or self.created_at


class CustomerNote(models.Model):
    """Quick freeform note attached to a customer (separate from Interaction
    for cases where the merchant wants persistent context rather than a log
    entry — e.g. allergies, VIP status, communication preferences)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE, related_name='crm_notes',
    )
    body = models.TextField()
    is_pinned = models.BooleanField(default=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='authored_crm_notes',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']
