"""dead_link healer — write seo.Redirect rows that 301 the broken URL
to a canonical destination.

Phase 2: only handles the trivial case where the URL's slug matches a
real product/category once trailing slashes / case are normalised
(e.g. `/products/Peter-Pan` → `/products/peter-pan/`). Phase 3 will
add LLM-driven fuzzy matching for typos and renames.
"""

from __future__ import annotations

import logging

from core.self_improvement.healers.base import Healer, HealResult, register_healer

logger = logging.getLogger('morpheus.self_improvement.healers.redirect')


@register_healer('redirect')
class RedirectHealer(Healer):
    def propose(self, recommendation) -> dict:
        pairs = self._candidate_pairs(recommendation)
        return {
            'kind': 'apply_data',
            'files': [],
            'patch': None,
            'data_changes': [
                {'model': 'seo.Redirect', 'from': frm, 'to': to} for frm, to in pairs[:25]
            ],
            'count': len(pairs),
        }

    def safe_to_apply(self, recommendation) -> tuple[bool, str]:
        if not recommendation.is_customization_safe:
            return False, 'customization_blocks_auto_apply'
        pairs = self._candidate_pairs(recommendation)
        if not pairs:
            return False, 'no_resolvable_redirects'
        if len(pairs) > 30:
            return False, 'too_many_redirects_for_one_run'
        return True, ''

    def apply(self, recommendation) -> HealResult:
        from django.apps import apps  # noqa: PLC0415

        try:
            Redirect = apps.get_model('seo', 'Redirect')
        except LookupError:
            return HealResult(ok=False, error='seo.Redirect not installed')

        created = 0
        for frm, to in self._candidate_pairs(recommendation):
            _, was_created = Redirect.objects.get_or_create(
                from_path=frm,
                defaults={'to_path': to, 'status_code': 301, 'is_active': True},
            )
            if was_created:
                created += 1
        return HealResult(ok=True, details={'created': created})

    # ----------------------------------------------------------------

    def _candidate_pairs(self, recommendation) -> list[tuple[str, str]]:
        from core.self_improvement.models import SiSignal  # noqa: PLC0415

        out = []
        seen = set()
        for s in SiSignal.objects.filter(pk__in=recommendation.evidence_signal_ids):
            payload = s.payload or {}
            url = payload.get('url') or payload.get('path') or ''
            canonical = self._normalise(url)
            if not url or not canonical or url == canonical:
                continue
            key = (url, canonical)
            if key in seen:
                continue
            seen.add(key)
            out.append(key)
        return out

    @staticmethod
    def _normalise(url: str) -> str:
        """Strip query, lower-case the slug, ensure trailing slash."""
        if not url:
            return ''
        path = url.split('?', 1)[0].split('#', 1)[0]
        if not path:
            return ''
        # Lower-case only the last path component (slug).
        parts = path.rstrip('/').rsplit('/', 1)
        if len(parts) == 2:
            parts[1] = parts[1].lower()
            path = '/'.join(parts)
        if not path.endswith('/'):
            path += '/'
        return path
