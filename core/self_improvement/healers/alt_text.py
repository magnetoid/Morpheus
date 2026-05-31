"""seo_gap healer — fill missing ProductImage.alt_text from product
name + position (e.g. "Peter Pan — cover").

Phase 2 is deliberately deterministic (no LLM). When a shop opts into
LLM-generated alt text (Phase 3), this healer's _generate() method will
delegate to ai_content.bulk_catalog.
"""

from __future__ import annotations

import logging

from core.self_improvement.healers.base import Healer, HealResult, register_healer

logger = logging.getLogger('morpheus.self_improvement.healers.alt_text')


@register_healer('alt_text')
class AltTextHealer(Healer):
    def propose(self, recommendation) -> dict:
        image_ids = self._image_ids(recommendation)
        return {
            'kind': 'apply_data',
            'files': [],
            'patch': None,
            'data_changes': [
                {'model': 'catalog.ProductImage', 'pk': str(pk), 'field': 'alt_text'}
                for pk in image_ids[:25]
            ],
            'count': len(image_ids),
        }

    def safe_to_apply(self, recommendation) -> tuple[bool, str]:
        if not recommendation.is_customization_safe:
            return False, 'customization_blocks_auto_apply'
        image_ids = self._image_ids(recommendation)
        if not image_ids:
            return False, 'no_target_images'
        if len(image_ids) > 50:
            return False, 'too_many_images_for_one_run'
        return True, ''

    def apply(self, recommendation) -> HealResult:
        try:
            from django.apps import apps  # noqa: PLC0415

            ProductImage = apps.get_model('catalog', 'ProductImage')
        except LookupError:
            return HealResult(ok=False, error='catalog.ProductImage not installed')

        image_ids = self._image_ids(recommendation)
        if not image_ids:
            return HealResult(ok=False, error='no targets')

        updated = 0
        for img in ProductImage.objects.filter(pk__in=image_ids, alt_text=''):
            alt = self._generate(img)
            if not alt:
                continue
            img.alt_text = alt[:255]
            img.save(update_fields=['alt_text'])
            updated += 1
        return HealResult(ok=updated > 0, details={'updated': updated})

    def verify(self, recommendation) -> HealResult:
        from django.apps import apps  # noqa: PLC0415

        try:
            ProductImage = apps.get_model('catalog', 'ProductImage')
        except LookupError:
            return HealResult(ok=False, error='catalog.ProductImage not installed')
        image_ids = self._image_ids(recommendation)
        remaining = ProductImage.objects.filter(pk__in=image_ids, alt_text='').count()
        return HealResult(
            ok=remaining == 0,
            details={'remaining_empty': remaining},
        )

    # ----------------------------------------------------------------

    def _image_ids(self, recommendation) -> list:
        from core.self_improvement.models import SiSignal  # noqa: PLC0415

        ids = []
        for s in SiSignal.objects.filter(pk__in=recommendation.evidence_signal_ids):
            payload = s.payload or {}
            if payload.get('gap') == 'product_image_alt':
                pk = payload.get('image_pk')
                if pk:
                    ids.append(pk)
        return list(dict.fromkeys(ids))

    @staticmethod
    def _generate(image) -> str:
        product = getattr(image, 'product', None)
        product_name = getattr(product, 'name', '') or ''
        is_primary = getattr(image, 'is_primary', False)
        sort_order = getattr(image, 'sort_order', 0)
        if not product_name:
            return ''
        if is_primary or sort_order == 0:
            return f'{product_name} — cover'
        if sort_order == 1:
            return f'{product_name} — back cover'
        return f'{product_name} — detail {sort_order}'
