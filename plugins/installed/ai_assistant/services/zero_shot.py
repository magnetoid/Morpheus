"""Zero-shot catalog classification.

Given product text + a set of candidate labels, the active LLM picks the
best-fitting labels with no training data. Gated by the `enable_zero_shot_catalog`
flag (Settings → AI) — exposed to Linda as the `catalog.classify_product` tool.

Generic by design: `classify(text, labels)` knows nothing about books or
catalog models; `classify_product(product)` is the catalog convenience that
defaults the candidate labels to the store's category names.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.ai_assistant')

_SYSTEM = (
    'You are a precise catalog classifier. You output STRICT JSON only — '
    'no prose, no markdown fences.'
)


def classify(text: str, labels: list[str], *, max_labels: int = 3) -> dict:
    """Zero-shot: pick the best-fitting `labels` for `text`.

    Returns ``{'labels': [...]}`` (a subset of the candidates, exact spelling,
    deduped, capped at `max_labels`) or ``{'labels': [], 'error': ...}``. Never
    raises — fail-soft so a classification call can't break a chat turn.
    """
    text = (text or '').strip()
    candidates = [str(label).strip() for label in (labels or []) if str(label).strip()]
    if not text or not candidates:
        return {'labels': [], 'error': 'text and candidate labels are both required'}

    try:
        from plugins.installed.ai_assistant.services.llm import get_llm  # noqa: PLC0415

        llm = get_llm()
    except Exception as e:  # noqa: BLE001
        logger.warning('zero_shot: LLM unavailable: %s', e)
        return {'labels': [], 'error': f'LLM unavailable: {e}'}

    prompt = (
        f'Classify the text into AT MOST {max_labels} of the candidate labels. '
        'Use the EXACT spelling from the list; pick only genuinely-fitting labels '
        '(fewer is better than forcing a poor fit). Candidate labels:\n'
        f'{", ".join(candidates)}\n\n'
        f'Text:\n{text[:1500]}\n\n'
        'Return STRICT JSON, nothing else: {"labels": ["..."]}'
    )
    try:
        raw = llm.complete(prompt, system=_SYSTEM, temperature=0.1, max_tokens=300)

        from core.llm_parsing import parse_llm_json  # noqa: PLC0415

        data = parse_llm_json(raw or '')
    except Exception as e:  # noqa: BLE001
        logger.warning('zero_shot: classify failed: %s', e)
        return {'labels': [], 'error': str(e)[:200]}

    # Keep only candidates the model actually returned, case-insensitively, in
    # the model's order, deduped — never invent a label outside the candidate set.
    allowed = {c.lower(): c for c in candidates}
    picked: list[str] = []
    raw_labels = data.get('labels') if isinstance(data, dict) else []
    for label in raw_labels or []:
        canon = allowed.get(str(label).strip().lower())
        if canon and canon not in picked:
            picked.append(canon)
    return {'labels': picked[:max_labels]}


def classify_product(product, labels: list[str] | None = None, *, max_labels: int = 3) -> dict:
    """Classify a catalog `product`. When `labels` is omitted, the store's
    category names are used as the candidate set."""
    name = getattr(product, 'name', '') or ''
    desc = (
        getattr(product, 'description', '')
        or getattr(product, 'short_description', '')
        or getattr(product, 'meta_description', '')
        or ''
    )
    text = '. '.join(part for part in (name, str(desc)) if part)

    if not labels:
        from plugins.installed.catalog.models import Category  # noqa: PLC0415

        labels = list(Category.objects.values_list('name', flat=True))
    return classify(text, labels, max_labels=max_labels)
