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
from morpheus.app import models


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
    # Blank means "whatever this page kind is" — which is almost always what a
    # merchant wants. It used to default to a non-blank 'website', and because
    # `autofill_meta_for` mints a row for every product on creation, EVERY
    # product page then declared `og:type=website` instead of `product`: the
    # value outranked the page kind in resolve_meta, and nothing in the panel,
    # the product form, GraphQL or the agent tools ever wrote the field, so no
    # merchant had chosen it. Share cards were wrong storewide and nothing said so.
    og_type = models.CharField(max_length=20, choices=OG_TYPE_CHOICES, blank=True, default='')
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
        help_text=(
            'LEGACY. Was emitted as <meta name="keywords">, which every major '
            'engine has ignored since 2009 — and the panel that wrote it was '
            'labelled "internal", so a merchant\'s private focus keyword was '
            'published on the page. Nothing reads this now; use focus_keyword.'
        ),
    )
    # ── Merchant-owned fields that used to live as native columns on the host
    # model (catalog.Product had thirteen of them, Category/Collection two).
    # SeoMeta is the single owner as of v0.47: the native columns are still READ
    # as a fallback (resolve_meta), but every editor writes here, so one panel
    # serves products, categories, collections, pages and vendors alike.
    focus_keyword = models.CharField(
        max_length=120,
        blank=True,
        help_text=(
            'The query this page is written for. Internal only — it drives the '
            "panel's checks and the SEO score, and is never emitted as markup."
        ),
    )
    twitter_title = models.CharField(max_length=200, blank=True)
    twitter_description = models.CharField(max_length=320, blank=True)
    robots_extra = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            'Advanced robots directives beyond index/follow — any of '
            'max_snippet (int), max_image_preview ("none"|"standard"|"large"), '
            'max_video_preview (int), nosnippet (bool), noimageindex (bool), '
            'unavailable_after (ISO 8601 date). These are also what gates how '
            'much of the page may appear inside AI Overviews / AI Mode.'
        ),
    )
    sitemap_include = models.BooleanField(
        null=True,
        blank=True,
        help_text=(
            'Tri-state override: NULL keeps the platform default for this page '
            'kind, True forces the URL into the sitemap, False keeps it out. A '
            'noindex page is never included regardless.'
        ),
    )
    ai_answer = models.TextField(
        blank=True,
        max_length=600,
        help_text=(
            'A quotable, factual TL;DR an answer engine can lift verbatim. '
            'Powers the on-page key-facts block and disambiguatingDescription. '
            'Was the seo.ai_answer metafield; read-through fallback remains.'
        ),
    )
    provenance = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            'Per-field origin: {"title": "merchant"|"ai"|"template"|"migrated"}. '
            'Lets the panel show where a value came from, and lets a bulk '
            'template or AI pass skip anything the merchant wrote by hand.'
        ),
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
    """One rule mapping an old path to a new one — or to nothing (410).

    Three match types, and the order they are tried in is the whole design:
    an **exact** row always beats a **prefix** row, which beats a **regex**
    row. Without that precedence a broad ``/books/`` prefix rule silently
    swallows the specific ``/books/dune/`` rule a merchant added afterwards,
    and the only symptom is a page quietly serving the wrong redirect.
    """

    KIND_CHOICES = [
        (301, 'Permanent (301)'),
        (302, 'Temporary (302)'),
        (307, 'Temporary, keep method (307)'),
        (308, 'Permanent, keep method (308)'),
        # 410 is not a redirect: it tells an engine the URL is gone for good
        # and to drop it from the index, which is what a deleted product wants
        # (a 404 leaves it in the index far longer).
        (410, 'Gone (410) — removed for good'),
    ]
    MATCH_EXACT = 'exact'
    MATCH_PREFIX = 'prefix'
    MATCH_REGEX = 'regex'
    MATCH_CHOICES = [
        (MATCH_EXACT, 'Exact path'),
        (MATCH_PREFIX, 'Path prefix'),
        (MATCH_REGEX, 'Regular expression'),
    ]
    SOURCE_CHOICES = [
        ('manual', 'Added by hand'),
        ('auto_slug', 'Created automatically when a slug changed'),
        ('import', 'Imported from CSV'),
        ('404_fix', 'Created from the 404 log'),
        ('agent', 'Created by an assistant'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_path = models.CharField(max_length=500, db_index=True)
    to_path = models.CharField(max_length=500, blank=True)
    status_code = models.PositiveSmallIntegerField(choices=KIND_CHOICES, default=301)
    match_type = models.CharField(
        max_length=10, choices=MATCH_CHOICES, default=MATCH_EXACT, db_index=True
    )
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default='manual')
    is_active = models.BooleanField(default=True, db_index=True)
    note = models.CharField(max_length=200, blank=True)
    hit_count = models.PositiveIntegerField(default=0)
    last_hit_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['from_path']
        # Was unique on from_path alone, which made an exact rule and a prefix
        # rule for the same path mutually exclusive for no reason.
        constraints = [
            models.UniqueConstraint(
                fields=['from_path', 'match_type'], name='seo_redirect_unique_rule'
            )
        ]

    def __str__(self) -> str:
        if self.status_code == 410:
            return f'{self.from_path} → gone (410)'
        return f'{self.from_path} → {self.to_path}'

    @property
    def is_gone(self) -> bool:
        return self.status_code == 410

    def save(self, *args, **kwargs):
        """Normalise the paths and collapse the chain before storing.

        This belongs on the model rather than in the dashboard view: rules also
        arrive from CSV import, the 404 log, an assistant, and the automatic
        slug watcher, and every one of those paths needs the same treatment. A
        rule whose `from_path` was never normalised simply never fires.

        Cache invalidation is deliberately NOT here — it hangs off post_save /
        post_delete (see signals.py), because a `QuerySet.update()` skips this
        method entirely and a resolver serving a deleted rule is worse than a
        redundant cache drop.
        """
        from plugins.installed.seo.services.redirects import (
            collapse_chain,
            normalise_path,
            normalise_target,
        )

        # A regex rule's `from_path` IS a pattern — normalising it would eat the
        # anchors and character classes that make it work.
        if self.match_type != self.MATCH_REGEX:
            self.from_path = normalise_path(self.from_path)
        self.to_path = '' if self.status_code == 410 else normalise_target(self.to_path)
        if self.to_path and self.match_type == self.MATCH_EXACT:
            self.to_path = collapse_chain(self.from_path, self.to_path)
        super().save(*args, **kwargs)


class SlugHistory(models.Model):
    """Every public path an object has ever had.

    A merchant renaming a product renames its URL, and every link and ranking
    pointing at the old one dies silently — the single most common way an
    e-commerce site loses traffic to its own dashboard. Recording the old path
    lets the platform mint the 301 automatically, and keeps a trail so the
    redirect can be rebuilt if someone deletes it.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64)
    target = GenericForeignKey('content_type', 'object_id')

    old_path = models.CharField(max_length=500, db_index=True)
    new_path = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['content_type', 'object_id'])]

    def __str__(self) -> str:
        return f'{self.old_path} → {self.new_path}'


class IndexRule(models.Model):
    """What a query parameter does to a page's indexability.

    A storefront listing multiplies: `?sort=`, `?genre=`, `?price_min=`,
    `?utm_source=` and every combination of them is a distinct URL serving
    substantially the same products. Left alone that is thousands of near-
    duplicate pages competing with the category they came from, and a crawler
    spending its budget on permutations instead of products.

    One row per parameter, one of four policies — chosen because they are the
    four *different* things a merchant can mean, not because a fifth would be
    tidy:

    * **consolidate** — the canonical drops the parameter, the page stays
      indexable. The right answer for tracking and for `sort`/`view`: the
      content is the category, seen sideways.
    * **noindex** — the page is `noindex, follow` **and self-canonical**. The
      self-canonical is the part that is easy to get wrong: a page that says
      "don't index me" while pointing its canonical at another URL is sending
      two contradictory signals about two different URLs, and Google's
      documented behaviour is that the noindex may be applied to the canonical
      target — i.e. the category page itself can drop out. Pick one signal.
    * **allowlist** — named values are real landing pages (`?genre=fantasy`),
      self-canonical and indexable; every other value gets the noindex
      treatment. This is the one that earns a store traffic rather than just
      protecting it.
    * **block** — a `Disallow: /*?*param=` line in robots.txt. The only policy
      that saves crawl budget, because it stops the fetch instead of labelling
      the result; also the only one whose page-level directives are never seen,
      which is why it must not also try to noindex.

    `param` may end in `*` to match a family (`utm_*`), so the six UTM
    parameters plus whatever a campaign tool invents next are one row.
    """

    POLICY_CONSOLIDATE = 'consolidate'
    POLICY_NOINDEX = 'noindex'
    POLICY_ALLOWLIST = 'allowlist'
    POLICY_BLOCK = 'block'
    POLICY_CHOICES = [
        (POLICY_CONSOLIDATE, 'Keep indexable, drop from the canonical'),
        (POLICY_NOINDEX, 'No-index this page (self-canonical)'),
        (POLICY_ALLOWLIST, 'Index only the listed values'),
        (POLICY_BLOCK, 'Block in robots.txt'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    param = models.CharField(
        max_length=64,
        unique=True,
        help_text='Query parameter name. A trailing * matches a family, e.g. utm_*',
    )
    policy = models.CharField(max_length=16, choices=POLICY_CHOICES, default=POLICY_CONSOLIDATE)
    allowed_values = models.JSONField(
        default=list,
        blank=True,
        help_text='Values that stay indexable, for the "index only the listed values" policy.',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['param']
        verbose_name = 'Index rule'

    def __str__(self) -> str:
        return f'{self.param} → {self.get_policy_display()}'

    def save(self, *args, **kwargs):
        """Normalise on the model, not in the view.

        Rules arrive from the dashboard, from the seeding migration and from a
        shell, and a rule stored as ` UTM_Source ` matches nothing while looking
        entirely correct in the table.
        """
        self.param = (self.param or '').strip().lower()
        if not isinstance(self.allowed_values, list):
            self.allowed_values = []
        self.allowed_values = [str(v).strip() for v in self.allowed_values if str(v).strip()]
        super().save(*args, **kwargs)


class SeoTemplate(models.Model):
    """One title/description pattern for a whole page kind.

    A resolution layer, not a bulk write: nothing is stamped onto rows, so
    editing the pattern re-titles every page it covers on the next render and
    deleting it restores exactly what resolution produced before. A merchant's
    own typed value always beats an ``empty_only`` template (the P1 lesson);
    ``all`` mode is the deliberate opposite — "brand every product title like
    this, including the ones typed before the pattern existed".

    ``scope`` narrows a rule to one category (by slug — matches both ORM
    products and the PDP's GraphQL dict); empty means every page of the kind.
    Lowest ``priority`` wins; scoped rules beat global at equal priority.
    Grammar + compiled cache: ``services/templating.py``.
    """

    KIND_CHOICES = [
        ('product', 'Products'),
        ('listing', 'Category & collection pages'),
        ('article', 'Journal posts'),
        ('page', 'CMS pages'),
        ('static', 'Static pages'),
    ]
    FIELD_CHOICES = [('title', 'Meta title'), ('description', 'Meta description')]
    MODE_EMPTY_ONLY = 'empty_only'
    MODE_ALL = 'all'
    MODE_CHOICES = [
        (MODE_EMPTY_ONLY, 'Fill empty fields only'),
        (MODE_ALL, 'Override everything of this kind'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, db_index=True)
    field = models.CharField(max_length=20, choices=FIELD_CHOICES, default='title')
    scope = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text='Category slug to narrow this rule to; empty = every page of the kind.',
    )
    template = models.TextField(
        help_text='Pattern with {tokens} — e.g. {name} — buy online | {site_name}'
    )
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_EMPTY_ONLY)
    priority = models.PositiveIntegerField(default=100, help_text='Lower wins.')
    is_active = models.BooleanField(default=True)
    note = models.CharField(max_length=300, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['kind', 'field', 'priority', 'created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['kind', 'field', 'scope'], name='seo_template_one_per_scope'
            )
        ]

    def __str__(self) -> str:
        where = self.scope or 'all'
        return f'{self.get_kind_display()} {self.field} ({where})'

    def save(self, *args, **kwargs):
        self.scope = (self.scope or '').strip().lower()
        self.template = (self.template or '').strip()
        super().save(*args, **kwargs)


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

    # Redirects
    auto_redirect_on_slug_change = models.BooleanField(
        default=True,
        help_text=(
            'When a product, category, collection or page is renamed, keep the '
            'old URL working with a 301 to the new one. Off means renaming a '
            'page breaks every existing link to it.'
        ),
    )
    block_homepage_redirects = models.BooleanField(
        default=True,
        help_text=(
            'Refuse redirects that point at the homepage. Bulk-redirecting dead '
            'URLs to "/" reads as a soft 404 to search engines and loses the '
            'page rather than moving it — leave this on unless you mean it.'
        ),
    )

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
