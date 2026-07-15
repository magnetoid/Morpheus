"""Book Product — a product-type extension that turns a catalog Product into a
rich book.

The book's *attributes* (author, print/paper type, page count, cover PDF, …)
live here as real columns rather than loose metafields, so they're queryable
and schema-checked. ISBN/EAN/GTIN identifiers intentionally stay in the
`identifiers` metafield namespace (they're identifiers, not book attributes);
this model cross-references them via the product.
"""

from __future__ import annotations

import uuid

from django.db import models


class PrintType(models.TextChoices):
    HARDCOVER = 'hardcover', 'Hardcover'
    PAPERBACK = 'paperback', 'Paperback'
    MASS_MARKET = 'mass_market', 'Mass-market paperback'
    BOARD_BOOK = 'board_book', 'Board book'
    SPIRAL = 'spiral', 'Spiral / wire-o'
    LEATHER = 'leather', 'Leather / cloth bound'
    EBOOK = 'ebook', 'E-book'
    AUDIOBOOK = 'audiobook', 'Audiobook'


class PaperType(models.TextChoices):
    STANDARD = 'standard', 'Standard white'
    CREAM = 'cream', 'Cream / off-white'
    COATED_GLOSS = 'coated_gloss', 'Coated gloss'
    COATED_MATTE = 'coated_matte', 'Coated matte'
    UNCOATED = 'uncoated', 'Uncoated'
    RECYCLED = 'recycled', 'Recycled'


class _CuratedTaxonomy(models.Model):
    """Shared shape for the curated, multi-value book taxonomies (Genre, Topic).

    Unlike author/publisher/series/imprint (single string fields auto-discovered
    from BookProduct), genres and topics are curated rows a book belongs to many
    of — so they're real models with their own landing-page SEO, mirroring how a
    Category/Collection is edited. Flat (no parent): a deliberate SEO choice —
    shallow, content-rich pages over thin nested sub-genres.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    image = models.ImageField(upload_to='book_taxonomies/', null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['sort_order', 'name']

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify  # noqa: PLC0415

            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Genre(_CuratedTaxonomy):
    """A literary genre (Fiction, Poetry, Essays, …). The primary book taxonomy
    the storefront browses by — replaces the old catalog-Category-as-genre."""


class Topic(_CuratedTaxonomy):
    """A subject/theme tag (WWII, grief, space exploration). A second, flat axis
    that intersects Genre to cover the long-tail without nested sub-genres."""


class BookProduct(models.Model):
    """Book-specific attributes for a catalog Product (one-to-one)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.OneToOneField('catalog.Product', on_delete=models.CASCADE, related_name='book')

    # ── Curated taxonomies (multi-value) ───────────────────────────────────
    genres = models.ManyToManyField(Genre, blank=True, related_name='books')
    topics = models.ManyToManyField(Topic, blank=True, related_name='books')

    # ── Bibliographic ──────────────────────────────────────────────────────
    author = models.CharField(max_length=300, blank=True)
    subtitle = models.CharField(max_length=300, blank=True)
    # [{'role': 'Translator', 'name': '...'}, ...] — illustrator/editor/etc.
    contributors = models.JSONField(default=list, blank=True)
    publisher = models.CharField(max_length=200, blank=True)
    imprint = models.CharField(max_length=200, blank=True)
    publication_date = models.DateField(null=True, blank=True)
    edition = models.CharField(max_length=100, blank=True)
    language = models.CharField(max_length=20, blank=True, default='en')
    # Language editions: a translated edition points at the ORIGINAL work's
    # book row. Each edition is a full Product (own slug, own-language copy,
    # own print/ebook/audiobook variants); this link powers the PDP language
    # switcher + hreflang alternates. SET_NULL: deleting the original leaves
    # translations standalone rather than cascading whole products away.
    translation_of = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='translations',
    )
    series = models.CharField(max_length=200, blank=True)
    series_position = models.CharField(max_length=40, blank=True)
    synopsis = models.TextField(blank=True)

    # ── Physical ───────────────────────────────────────────────────────────
    print_type = models.CharField(
        max_length=20, choices=PrintType.choices, default=PrintType.PAPERBACK
    )
    paper_type = models.CharField(max_length=20, choices=PaperType.choices, blank=True)
    binding = models.CharField(max_length=100, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    # Millimetres — drive the 3D viewer's book proportions (spine = thickness).
    width_mm = models.PositiveIntegerField(null=True, blank=True)
    height_mm = models.PositiveIntegerField(null=True, blank=True)
    spine_mm = models.PositiveIntegerField(null=True, blank=True)
    weight_g = models.PositiveIntegerField(null=True, blank=True)

    # ── Cover PDF (drives the three.js 3D preview) ─────────────────────────
    cover_pdf = models.FileField(upload_to='book_covers/', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Book product'
        verbose_name_plural = 'Book products'

    def __str__(self) -> str:
        return f'{self.author} — {self.product_id}' if self.author else str(self.product_id)

    def language_editions(self) -> list[BookProduct]:
        """Every edition of this work (the original + all translations),
        including self, with an active product — original first, then by
        language. Powers the PDP language switcher + hreflang alternates."""
        original = self.translation_of or self
        ids = [original.pk, *original.translations.values_list('pk', flat=True)]
        rows = list(
            BookProduct.objects.filter(pk__in=ids, product__status='active').select_related(
                'product'
            )
        )
        rows.sort(key=lambda b: (b.pk != original.pk, b.language or ''))
        return rows


class BookTaxonomy(models.TextChoices):
    AUTHOR = 'author', 'Author'
    PUBLISHER = 'publisher', 'Publisher'
    SERIES = 'series', 'Series'
    IMPRINT = 'imprint', 'Imprint'


class BookTaxonomyTerm(models.Model):
    """Per-term SEO/metadata overlay for a book taxonomy value.

    Terms (a given author, publisher, series, imprint) derive from BookProduct
    field values; a row here exists only when the merchant customizes one's
    landing page — its SEO + intro blurb + image — exactly like editing a
    Category/Collection. The facet page (/author/<slug>/ etc.) renders it.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    taxonomy = models.CharField(max_length=20, choices=BookTaxonomy.choices, db_index=True)
    slug = models.SlugField(max_length=200, db_index=True)
    name = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    image = models.ImageField(upload_to='book_taxonomies/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('taxonomy', 'slug')]
        verbose_name = 'Book taxonomy term'
        verbose_name_plural = 'Book taxonomy terms'

    def __str__(self) -> str:
        return f'{self.get_taxonomy_display()}: {self.name}'


class BookTaxonomyRoot(models.Model):
    """The landing page for a whole taxonomy kind (e.g. /authors/).

    One row per BookTaxonomy kind, holding the editable intro blurb, SEO, and
    hero image the listing page renders — the same widgets as a term, but for
    the root listing rather than a single author/publisher/series/imprint.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    taxonomy = models.CharField(max_length=20, choices=BookTaxonomy.choices, unique=True)
    description = models.TextField(blank=True)
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    image = models.ImageField(upload_to='book_taxonomies/', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Book taxonomy root page'
        verbose_name_plural = 'Book taxonomy root pages'

    def __str__(self) -> str:
        return f'{self.get_taxonomy_display()} root page'
