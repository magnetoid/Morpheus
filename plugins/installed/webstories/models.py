"""Web Stories model.

One ``WebStory`` per Product. ``panels`` is a JSON list of panel
dicts — keeping it denormalized lets the auto-builder regenerate
the whole story in one query without juggling FK rows.

Panel shape::

    {
      "image_url": "/media/products/foo.jpg",
      "title":     "Optional large overlay headline",
      "caption":   "Optional body text",
      "cta_url":   "/products/foo/",       # final panel only
      "cta_label": "View product",         # final panel only
    }
"""

from __future__ import annotations

from django.db import models

#: Google's floor for a Web Story (it recommends five to thirty pages). A
#: shorter story still plays in the product page's player, but is kept out of
#: search: robots noindex, and no sitemap entry.
MIN_INDEXABLE_PAGES = 4


class WebStory(models.Model):
    product = models.OneToOneField(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='web_story',
    )
    title = models.CharField(max_length=120, blank=True)
    summary = models.CharField(max_length=280, blank=True)
    panels = models.JSONField(default=list, blank=True)
    poster_portrait_url = models.CharField(max_length=500, blank=True)
    is_published = models.BooleanField(default=True, db_index=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Web Story'
        verbose_name_plural = 'Web Stories'

    def __str__(self) -> str:
        return f'WebStory({self.product.slug})'

    @property
    def slug(self) -> str:
        return self.product.slug

    @property
    def panel_count(self) -> int:
        return len(self.panels or [])

    @property
    def is_indexable(self) -> bool:
        """May search engines index this story? The one rule the story page's
        robots meta and the sitemap both read: published, long enough, and its
        product not hidden from search (a pre-launch product's story must not
        leak it)."""
        return (
            self.is_published
            and self.panel_count >= MIN_INDEXABLE_PAGES
            and not getattr(self.product, 'noindex', False)
        )
