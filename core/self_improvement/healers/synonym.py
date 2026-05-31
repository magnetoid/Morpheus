"""zero_search healer — add synonym mappings for high-volume
queries that returned zero results.

Phase 2: deterministic stem matcher — find products whose name
contains a *single* word from the failed query. Phase 3 will use
embeddings + LLM rephrase.
"""

from __future__ import annotations

import logging
import re

from core.self_improvement.healers.base import Healer, HealResult, register_healer

logger = logging.getLogger('morpheus.self_improvement.healers.synonym')

MIN_SEEN_COUNT = 10
TOPK_SUGGESTIONS = 3


@register_healer('synonym')
class SynonymHealer(Healer):
    def propose(self, recommendation) -> dict:
        candidates = self._candidates(recommendation)
        return {
            'kind': 'apply_data',
            'files': [],
            'patch': None,
            'data_changes': [
                {'model': 'catalog.SearchSynonym', 'term': c['term'], 'maps_to': c['maps_to']}
                for c in candidates[:25]
            ],
            'count': len(candidates),
        }

    def safe_to_apply(self, recommendation) -> tuple[bool, str]:
        if not recommendation.is_customization_safe:
            return False, 'customization_blocks_auto_apply'
        candidates = self._candidates(recommendation)
        if not candidates:
            return False, 'no_resolvable_synonyms'
        return True, ''

    def apply(self, recommendation) -> HealResult:
        from django.apps import apps  # noqa: PLC0415

        try:
            SearchSynonym = apps.get_model('catalog', 'SearchSynonym')
        except LookupError:
            return HealResult(ok=False, error='catalog.SearchSynonym not installed')

        created = 0
        for c in self._candidates(recommendation):
            _, was_created = SearchSynonym.objects.get_or_create(
                term=c['term'][:64],
                defaults={'maps_to': c['maps_to'][:200], 'is_active': True},
            )
            if was_created:
                created += 1
        return HealResult(ok=created > 0, details={'created': created})

    # ----------------------------------------------------------------

    def _candidates(self, recommendation) -> list[dict]:
        from core.self_improvement.models import SiSignal  # noqa: PLC0415

        # Aggregate the queries from the zero_search signals.
        rows = list(
            SiSignal.objects.filter(pk__in=recommendation.evidence_signal_ids, source='zero_search')
        )
        if not rows:
            return []
        # Only suggest synonyms for queries with enough volume.
        terms = []
        for s in rows:
            if s.seen_count < MIN_SEEN_COUNT:
                continue
            q = (s.payload or {}).get('query') or ''
            if q:
                terms.append(q.strip().lower())

        results = []
        for term in terms[:25]:
            mapped = self._find_mapping(term)
            if mapped:
                results.append({'term': term, 'maps_to': mapped})
        return results

    @staticmethod
    def _find_mapping(term: str) -> str:
        """Find an existing product whose name shares ≥ 1 substantive word
        with the failed query. Returns a comma-separated list of matched
        product names (top-K) for the synonym row."""
        from django.apps import apps  # noqa: PLC0415

        try:
            Product = apps.get_model('catalog', 'Product')
        except LookupError:
            return ''

        words = [w for w in re.findall(r'\w+', term.lower()) if len(w) >= 4]
        if not words:
            return ''

        from django.db.models import Q  # noqa: PLC0415

        q_obj = Q()
        for w in words:
            q_obj |= Q(name__icontains=w)
        matches = Product.objects.filter(q_obj, status='active').values_list('name', flat=True)[
            :TOPK_SUGGESTIONS
        ]
        names = list(matches)
        return ', '.join(names) if names else ''
