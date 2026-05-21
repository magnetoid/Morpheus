"""Perf indexes for hot-path queries.

Three composite indexes that the storefront PDP/PLP hits on every
render:

- catalog_product_status_cat_idx — Product.objects.filter(
  status='active', category=X) is the canonical PLP/category query.
  Composite covers status + category without falling back to the
  category-only index + filter.

- catalog_image_product_sort_idx — PDP fetches
  product.images.all().order_by('sort_order'); composite returns
  the ordered set directly instead of in-memory sort.

- catalog_review_pdp_idx — Review.objects.filter(product=X,
  is_approved=True).order_by('-helpful_votes', '-created_at') is
  the "Reader letters" PDP block.

Indexes only — no schema changes. Safe to apply on a live database.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0008_productimage_webp_image'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='product',
            index=models.Index(
                fields=['status', 'category'],
                name='catalog_product_status_cat_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='productimage',
            index=models.Index(
                fields=['product', 'sort_order'],
                name='catalog_image_product_sort_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='review',
            index=models.Index(
                fields=['product', 'is_approved', '-helpful_votes'],
                name='catalog_review_pdp_idx',
            ),
        ),
    ]
