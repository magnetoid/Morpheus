"""
Base importer abstraction.

Importers are stateless adapters that yield records (dicts) from a source,
and call back into the platform's domain models. They MUST upsert via
SourceMapping so re-runs are idempotent.

Usage:

    from plugins.installed.importers.adapters.shopify import ShopifyImporter

    importer = ShopifyImporter(shop='my-shop', token='...')
    summary = importer.run()
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from django.db import DatabaseError
from django.utils import timezone

logger = logging.getLogger('morpheus.importers')


@dataclass
class ImportSummary:
    counts: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def increment(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n


class BaseImporter:
    """Subclass and implement `iter_*` methods + `run`."""

    source: str = ''  # 'shopify' | 'woocommerce' | ...

    def __init__(self) -> None:
        if not self.source:
            raise ValueError('Importer subclass must set `source`')
        self.summary = ImportSummary()

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self, *, started_by: str = '') -> ImportSummary:
        """Top-level entry point. Subclasses can override for custom orchestration."""
        from plugins.installed.importers.models import ImportRun

        run = None
        try:
            run = ImportRun.objects.create(source=self.source, started_by=started_by)
        except DatabaseError as e:
            logger.warning('importers: could not create ImportRun: %s', e)

        try:
            self._run()
            status = 'succeeded'
        except Exception as e:  # noqa: BLE001 — capture, then mark run failed
            self.summary.errors.append(str(e))
            status = 'failed'
            logger.error('importers: %s run failed: %s', self.source, e, exc_info=True)
            raise
        finally:
            if run is not None:
                try:
                    run.status = status if 'status' in dir() and status else 'failed'
                    run.counts = self.summary.counts
                    run.errors = self.summary.errors
                    run.finished_at = timezone.now()
                    run.save(update_fields=['status', 'counts', 'errors', 'finished_at'])
                except DatabaseError as e:
                    logger.warning('importers: could not finalize ImportRun: %s', e)

        return self.summary

    def _run(self) -> None:
        raise NotImplementedError

    # ── SourceMapping helpers ─────────────────────────────────────────────────

    def upsert(
        self,
        *,
        source_id: str,
        dest_obj,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Idempotent: link a source_id to a Morpheus model instance."""
        from plugins.installed.importers.models import SourceMapping

        SourceMapping.objects.update_or_create(
            source=self.source,
            source_id=str(source_id),
            dest_model=type(dest_obj).__name__,
            defaults={
                'dest_app': type(dest_obj)._meta.app_label,
                'dest_pk': str(dest_obj.pk),
                'metadata': dict(metadata or {}),
            },
        )

    def find_existing(self, *, source_id: str, dest_model: str) -> str | None:
        from plugins.installed.importers.models import SourceMapping

        try:
            mapping = SourceMapping.objects.get(
                source=self.source,
                source_id=str(source_id),
                dest_model=dest_model,
            )
        except SourceMapping.DoesNotExist:
            return None
        return mapping.dest_pk
