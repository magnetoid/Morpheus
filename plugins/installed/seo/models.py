"""
SEO plugin — models.

`SeoMeta` is a per-object overlay (generic FK) that stores merchant-controlled
title / description / OG image / canonical / robots / structured-data hints.
Models opt in by querying `SeoMeta.for_obj(obj)` from their resolvers; the
plugin makes no assumptions about the host model.

`Redirect` is a small alias map. The plugin's middleware resolves a request
path against this table and 301s if a row exists. `hit_count` and
`last_hit_at` give merchants a sanity check for stale aliases.
"""

# ruff: noqa: I001, UP037
# Import grouping + the quoted self-referential return annotations
# (``'SeoMeta | None'``) are pre-existing house style for this module.

from __future__ import annotations

import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from morpheus import models


class SeoMeta(models.Model):
    """Per-object SEO override. Generic across any model in the platform."""

    ROBOTS_CHOICES = [
        ('index, follow', 'Index, follow'),
        ('noindex, follow', 'Noindex, follow'),
        ('index, nofollow', 'Index, nofollow'),
        ('noindex, nofollow', 'Noindex, nofollow'),
    ]
    OG_TYPE_CHOICES = [
        ('website', 'Website'),
        ('product', 'Product'),
        ('article', 'Article'),
        ('book', 'Book'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64)
    target = GenericForeignKey('content_type', 'object_id')

    title = models.CharField(max_length=200, blank=True)
    description = models.CharField(max_length=320, blank=True)
    og_title = models.CharField(max_length=200, blank=True)
    og_description = models.CharField(max_length=320, blank=True)
    og_image = models.URLField(max_length=600, blank=True)
    og_type = models.CharField(max_length=20, choices=OG_TYPE_CHOICES, default='website')
    twitter_card = models.CharField(
        max_length=20,
        default='summary_large_image',
        help_text='summary | summary_large_image | app | player',
    )
    canonical_url = models.URLField(max_length=600, blank=True)
    robots = models.CharField(max_length=40, choices=ROBOTS_CHOICES, default='index, follow')
    keywords = models.CharField(
        max_length=320,
        blank=True,
        help_text='Comma-separated. Most engines ignore this; included for completeness.',
    )
    structured_data = models.JSONField(
        default=dict,
        blank=True,
        help_text='Extra JSON-LD properties merged into the auto-generated payload.',
    )
    schema_blocks = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            'Visual schema editor entries [{type, data}, …] (FAQ, HowTo, Event, '
            '…). Built into standalone <script type="application/ld+json"> blocks '
            'at render time — distinct from the merged structured_data dict above.'
        ),
    )
    auto_filled = models.BooleanField(
        default=False, help_text='True if filled by AI; False if merchant-edited.'
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('content_type', 'object_id')
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self) -> str:
        return f'SeoMeta({self.content_type.app_label}.{self.content_type.model}/{self.object_id})'

    @classmethod
    def for_obj(cls, obj) -> 'SeoMeta | None':
        if obj is None:
            return None
        ct = ContentType.objects.get_for_model(type(obj))
        return cls.objects.filter(content_type=ct, object_id=str(obj.pk)).first()


class Redirect(models.Model):
    """301/302 alias from one path to another."""

    KIND_CHOICES = [(301, 'Permanent (301)'), (302, 'Temporary (302)')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_path = models.CharField(max_length=500, unique=True, db_index=True)
    to_path = models.CharField(max_length=500)
    status_code = models.PositiveSmallIntegerField(choices=KIND_CHOICES, default=301)
    is_active = models.BooleanField(default=True, db_index=True)
    note = models.CharField(max_length=200, blank=True)
    hit_count = models.PositiveIntegerField(default=0)
    last_hit_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['from_path']

    def __str__(self) -> str:
        return f'{self.from_path} → {self.to_path}'


class SitemapEntry(models.Model):
    """
    Optional precomputed sitemap entry. Most callers should let the
    sitemap.xml view generate entries on the fly from the catalog;
    this table is for *manual* additions (the homepage, journal posts,
    static pages a merchant wants in the sitemap).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.CharField(max_length=500, unique=True)
    changefreq = models.CharField(
        max_length=10,
        default='weekly',
        choices=[
            ('always', 'always'),
            ('hourly', 'hourly'),
            ('daily', 'daily'),
            ('weekly', 'weekly'),
            ('monthly', 'monthly'),
            ('yearly', 'yearly'),
            ('never', 'never'),
        ],
    )
    priority = models.DecimalField(max_digits=3, decimal_places=2, default=0.5)
    last_modified = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)


# ─────────────────────────────────────────────────────────────────────────────
# Deep-SEO extensions: site settings, audits, keyword tracking, 404 monitor.
# ─────────────────────────────────────────────────────────────────────────────


class SiteSeoSettings(models.Model):
    """Singleton-style site-wide SEO defaults.

    Populates JSON-LD `Organization` + `WebSite`; provides default OG image
    + Twitter handle when SeoMeta doesn't override; carries verification
    metas for Google Search Console / Bing / Pinterest.
    """

    TWITTER_CARD_CHOICES = [
        ('summary', 'Summary'),
        ('summary_large_image', 'Summary (large image)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization_name = models.CharField(max_length=200, blank=True)
    organization_logo_url = models.URLField(max_length=600, blank=True)
    default_og_image = models.URLField(max_length=600, blank=True)
    twitter_handle = models.CharField(max_length=50, blank=True, help_text='Without @')
    twitter_card_default = models.CharField(
        max_length=20,
        choices=TWITTER_CARD_CHOICES,
        default='summary_large_image',
    )

    # Social profiles → JSON-LD `sameAs`
    facebook_url = models.URLField(max_length=600, blank=True)
    instagram_url = models.URLField(max_length=600, blank=True)
    linkedin_url = models.URLField(max_length=600, blank=True)
    youtube_url = models.URLField(max_length=600, blank=True)
    tiktok_url = models.URLField(max_length=600, blank=True)

    # Search engine verification metas
    google_site_verification = models.CharField(max_length=120, blank=True)
    bing_verification = models.CharField(max_length=120, blank=True)
    pinterest_verification = models.CharField(max_length=120, blank=True)
    facebook_domain_verification = models.CharField(max_length=120, blank=True)

    # Sitelinks search
    enable_sitelinks_search = models.BooleanField(default=True)

    # AI / LLM discovery
    llms_txt_enabled = models.BooleanField(
        default=True,
        help_text='Serve /llms.txt for LLM crawlers (OpenAI, Anthropic, Perplexity, Google).',
    )
    llms_txt_intro = models.TextField(
        blank=True,
        help_text='Optional intro paragraph at the top of /llms.txt.',
    )
    ai_shopping_feed_enabled = models.BooleanField(
        default=True,
        help_text='Serve /ai/products.json — schema.org Product feed for AI shopping crawlers.',
    )
    ai_answer_block_enabled = models.BooleanField(
        default=False,
        help_text=(
            'Render a "Key facts / In short" answer block on product pages — a '
            'quotable TL;DR + spec table that AI answer engines (ChatGPT, '
            'Perplexity, AI Overviews) lift on-page. Off by default; needs an AI '
            'answer (seo.ai_answer metafield) or book metafields to show.'
        ),
    )

    # ── Structured data (JSON-LD) emission ───────────────────────────────
    # No-code control: pick which schema.org blocks the storefront emits,
    # straight from the SEO settings page — no edit to jsonld.py. All
    # default on, preserving current behaviour.
    jsonld_organization = models.BooleanField(
        default=True, help_text='Emit Organization JSON-LD site-wide.'
    )
    jsonld_website = models.BooleanField(
        default=True, help_text='Emit WebSite JSON-LD (+ sitelinks search box).'
    )
    jsonld_product = models.BooleanField(
        default=True, help_text='Emit Product JSON-LD on product pages.'
    )
    jsonld_reviews = models.BooleanField(
        default=True, help_text='Include aggregateRating + Review snippets inside Product JSON-LD.'
    )

    # Title formatting
    title_template = models.CharField(
        max_length=200,
        default='{title} — {site_name}',
        help_text='Variables: {title}, {site_name}, {category}',
    )
    title_max_length = models.PositiveSmallIntegerField(default=60)
    description_max_length = models.PositiveSmallIntegerField(default=155)

    # Robots directives
    noindex_query_params = models.JSONField(
        default=list,
        blank=True,
        help_text='Auto-add noindex on URLs that contain any of these query params (e.g. ["q","sort"])',
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site SEO settings'

    def __str__(self) -> str:
        return self.organization_name or 'Site SEO settings'

    @classmethod
    def get_solo(cls) -> 'SiteSeoSettings':
        instance, _ = cls.objects.get_or_create(pk=cls.objects.values_list('id', flat=True).first())
        return instance


class SeoAuditResult(models.Model):
    """Per-object SEO score + diagnostics. Refreshed on demand or by beat task."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64)
    target = GenericForeignKey('content_type', 'object_id')

    score = models.PositiveSmallIntegerField(default=0, db_index=True)  # 0–100
    issues = models.JSONField(
        default=list,
        help_text='List of {code, severity, message} dicts.',
    )
    suggestions = models.JSONField(default=list)
    audited_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('content_type', 'object_id')
        ordering = ['score']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['score', '-audited_at']),
        ]


class TrackedKeyword(models.Model):
    """A keyword the merchant cares about, optionally tied to a target page."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    keyword = models.CharField(max_length=200, db_index=True)
    target_url = models.CharField(max_length=500, blank=True)
    locale = models.CharField(max_length=10, default='en-US')
    notes = models.TextField(blank=True)
    last_position = models.PositiveSmallIntegerField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('keyword', 'locale')
        ordering = ['keyword']


class NotFoundLog(models.Model):
    """Aggregated 404 log — used to surface auto-redirect candidates."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    path = models.CharField(max_length=500, unique=True, db_index=True)
    hit_count = models.PositiveIntegerField(default=1)
    referrer = models.CharField(max_length=500, blank=True)
    last_seen_at = models.DateTimeField(auto_now=True, db_index=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    suggested_target = models.CharField(max_length=500, blank=True)
    is_resolved = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['-hit_count', '-last_seen_at']
