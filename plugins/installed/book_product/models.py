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


class BookProduct(models.Model):
    """Book-specific attributes for a catalog Product (one-to-one)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.OneToOneField('catalog.Product', on_delete=models.CASCADE, related_name='book')

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
