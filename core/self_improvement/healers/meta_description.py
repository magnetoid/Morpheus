"""seo_gap healer for missing Product.meta_description.

Phase 2: deterministic 140-180 char truncation of the product
description with sentence-boundary preference. The Phase 3 variant
delegates to ai_content.bulk_catalog.expand() for proper SEO copy.
"""

from __future__ import annotations

import logging

from core.self_improvement.healers.base import Healer, HealResult, register_healer

logger = logging.getLogger('morpheus.self_improvement.healers.meta_description')

TARGET_MAX = 160
TARGET_MIN = 100


@register_healer('meta_description')
class MetaDescriptionHealer(Healer):
    def propose(self, recommendation) -> dict:
        product_ids = self._product_ids(recommendation)
        return {
            'kind': 'apply_data',
            'files': [],
            'patch': None,
            'data_changes': [
                {'model': 'catalog.Product', 'pk': str(pk), 'field': 'meta_description'}
                for pk in product_ids[:25]
            ],
            'count': len(product_ids),
        }

    def safe_to_apply(self, recommendation) -> tuple[bool, str]:
        if not recommendation.is_customization_safe:
            return False, 'customization_blocks_auto_apply'
        product_ids = self._product_ids(recommendation)
        if not product_ids:
            return False, 'no_target_products'
        if len(product_ids) > 50:
            return False, 'too_many_products_for_one_run'
        return True, ''

    def apply(self, recommendation) -> HealResult:
        from django.apps import apps  # noqa: PLC0415

        try:
            Product = apps.get_model('catalog', 'Product')
        except LookupError:
            return HealResult(ok=False, error='catalog.Product not installed')

        product_ids = self._product_ids(recommendation)
        updated = 0
        for p in Product.objects.filter(pk__in=product_ids, meta_description=''):
            meta = self._summarise(p.description or '', fallback=p.name or '')
            if not meta:
                continue
            p.meta_description = meta
            p.save(update_fields=['meta_description'])
            updated += 1
        return HealResult(ok=updated > 0, details={'updated': updated})

    def verify(self, recommendation) -> HealResult:
        from django.apps import apps  # noqa: PLC0415

        try:
            Product = apps.get_model('catalog', 'Product')
        except LookupError:
            return HealResult(ok=False, error='catalog.Product not installed')
        product_ids = self._product_ids(recommendation)
        remaining = Product.objects.filter(pk__in=product_ids, meta_description='').count()
        return HealResult(ok=remaining == 0, details={'remaining_empty': remaining})

    # ----------------------------------------------------------------

    def _product_ids(self, recommendation) -> list:
        from core.self_improvement.models import SiSignal  # noqa: PLC0415

        ids = []
        for s in SiSignal.objects.filter(pk__in=recommendation.evidence_signal_ids):
            payload = s.payload or {}
            if payload.get('gap') == 'product_meta_description':
                pk = payload.get('product_pk')
                if pk:
                    ids.append(pk)
        return list(dict.fromkeys(ids))

    @staticmethod
    def _summarise(text: str, *, fallback: str) -> str:
        """Return a 100-160 char summary preferring sentence boundaries."""
        text = (text or '').strip()
        if not text:
            return (fallback or '')[:TARGET_MAX]
        # Try the first sentence (period/?/!) within range.
        for end_char in '.!?':
            idx = text.find(end_char, TARGET_MIN, TARGET_MAX)
            if idx > 0:
                return text[: idx + 1].strip()
        # Else hard truncate on word boundary near TARGET_MAX.
        if len(text) <= TARGET_MAX:
            return text
        cut = text[:TARGET_MAX]
        last_space = cut.rfind(' ')
        if last_space > TARGET_MIN:
            cut = cut[:last_space]
        return cut.rstrip(' ,;:-') + '…'
