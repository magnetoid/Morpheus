"""
Importer plugin — models.

`SourceMapping` records the mapping between an external system (Shopify, Woo,
Magento, BigCommerce, …) and the Morpheus row it produced. Importers MUST
upsert through this table so re-running an import is idempotent.
"""
from __future__ import annotations

import uuid

from morpheus import models


class SourceMapping(models.Model):
    """A `(source, source_id, dest_app, dest_model, dest_pk)` tuple."""

    SOURCE_CHOICES = [
        ('shopify', 'Shopify'),
        ('woocommerce', 'WooCommerce'),
        ('magento', 'Magento'),
        ('bigcommerce', 'BigCommerce'),
        ('csv', 'CSV'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, db_index=True)
    source_id = models.CharField(max_length=200, db_index=True)
    dest_app = models.CharField(max_length=100)
    dest_model = models.CharField(max_length=100)
    dest_pk = models.CharField(max_length=200, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    last_imported_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('source', 'source_id', 'dest_model')
        indexes = [
            models.Index(fields=['source', 'dest_model', '-last_imported_at']),
        ]

    def __str__(self) -> str:
        return f'{self.source}:{self.source_id} -> {self.dest_model}#{self.dest_pk}'


class ImportRun(models.Model):
    """A single run of an importer — for observability."""

    STATUS_CHOICES = [
        ('running', 'Running'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=20, db_index=True)
    started_by = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='running')
    counts = models.JSONField(default=dict)  # {"products": 100, "orders": 50}
    errors = models.JSONField(default=list)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
