"""Morpheus Brain — AI analysis (core).

Takes the gathered signals (code-quality + error-log findings from the immune
system, plugin health, SEO/content audits, storefront vitals) and asks the
*configured* AI provider (Settings → AI providers) to synthesize a short,
prioritized list of concrete improvements, new-feature ideas, and fixes,
grounded in the real signals and current engineering best practice.

Cheap to display: the LLM call is cached and refreshed on demand / on a beat
schedule, never on every page load. Degrades cleanly when no AI is configured.
"""

from __future__ import annotations

import contextlib
import json
import re
from typing import Any

from django.core.cache import cache

_CACHE_KEY = 'brain:analysis:v1'
_TTL = 60 * 60 * 24  # a day; refreshed by the beat task or the Refresh button

_SYSTEM = (
    'You are Morpheus Brain — the resident principal engineer for a modular '
    'Django e-commerce platform (Morpheus OS). You are given real, current '
    'signals about the running system: code-quality findings, recent error-log '
    'entries, plugin health, SEO/content audits, and storefront performance. '
    'Synthesize them into a SHORT, prioritized, ACTIONABLE plan. Prefer fixing '
    'real errors and code-quality findings over speculative ideas; propose new '
    'features only when the signals justify them. Apply current best practice '
    '(performance, security, accessibility, SEO, DX). Be specific and concrete; '
    'no filler. Respond with ONLY a JSON object, no prose, of the form:\n'
    '{"summary": "1-2 sentence state of the system", "recommendations": ['
    '{"title": "imperative, <=80 chars", "area": "code|errors|content|seo|'
    'storefront|plugins|feature", "priority": "high|medium|low", "why": '
    '"1-2 sentences citing the signal", "action": "the concrete next step"}]}'
)


def _summarize_signals(signals: dict) -> str:
    """A compact, token-cheap text digest of the signals for the prompt."""
    lines: list[str] = []
    code = signals.get('code') or {}
    if code.get('quality'):
        lines.append('CODE-QUALITY FINDINGS:')
        lines += [f'- (sev {q["severity"]}) {q["summary"]}' for q in code['quality'][:12]]
    if code.get('recommendations'):
        lines.append('EXISTING ENGINE RECOMMENDATIONS:')
        lines += [f'- [{r["class_name"]}] {r["title"]}' for r in code['recommendations'][:8]]
    if code.get('drift_count'):
        lines.append(f'Tracked customizations (drift): {code["drift_count"]}')
    errs = signals.get('errors') or {}
    if errs.get('recent'):
        lines.append('RECENT ERRORS:')
        lines += [
            f'- (x{e["seen_count"]}, sev {e["severity"]}) {e["summary"]}'
            for e in errs['recent'][:12]
        ]
    content = signals.get('content') or {}
    if content.get('catalog'):
        c = content['catalog']
        lines.append(
            f'CONTENT: {c.get("total", 0)} active products, '
            f'{c.get("missing_desc", 0)} missing a description.'
        )
    if content.get('seo_total'):
        lines.append(
            f'SEO: avg score {content.get("seo_avg")}, '
            f'{content.get("seo_low_count", 0)} below 50 (of {content["seo_total"]}).'
        )
    if content.get('notfound'):
        lines.append('TOP 404s: ' + ', '.join(n['path'] for n in content['notfound'][:6]))
    store = signals.get('storefront') or {}
    if store.get('cwv'):
        lines.append(f'CORE WEB VITALS (p75): {store["cwv"]}')
    plugins = signals.get('plugins') or {}
    if plugins.get('errors'):
        lines.append(
            'PLUGIN VALIDATION ISSUES: ' + '; '.join(str(e) for e in plugins['errors'][:6])
        )
    if plugins.get('total'):
        lines.append(f'PLUGINS: {plugins.get("active_count")}/{plugins["total"]} active.')
    return '\n'.join(lines) or 'No signals available yet.'


def _parse_json(text: str) -> dict | None:
    """Lenient JSON extraction from an LLM reply (strips code fences / prose)."""
    if not text:
        return None
    t = re.sub(r'^```(?:json)?|```$', '', text.strip(), flags=re.MULTILINE).strip()
    candidates = [t]
    start, end = t.find('{'), t.rfind('}')
    if start != -1 and end > start:
        candidates.append(t[start : end + 1])
    for c in candidates:
        with contextlib.suppress(ValueError, TypeError):
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
    return None


def analyze(signals: dict | None = None) -> dict[str, Any]:
    """Run the LLM over the signals → structured recommendations (uncached)."""
    from core.agents.llm import LLMMessage, get_llm_provider

    if signals is None:
        from core.brain.signals import gather_all

        signals = gather_all()

    provider = get_llm_provider()
    if getattr(provider, 'name', '') in ('unconfigured', 'mock', 'base'):
        return {
            'configured': False,
            'message': 'No AI provider is configured. Open Settings → AI providers, '
            'pick a provider and paste a key, then refresh this analysis.',
            'recommendations': [],
        }

    digest = _summarize_signals(signals)
    try:
        resp = provider.respond(
            messages=[
                LLMMessage(role='system', content=_SYSTEM),
                LLMMessage(role='user', content=f'Signals:\n{digest}\n\nReturn the JSON plan.'),
            ],
            temperature=0.4,
            max_tokens=1400,
        )
    except Exception as e:  # noqa: BLE001
        return {'configured': True, 'error': str(e)[:300], 'recommendations': []}

    parsed = _parse_json(getattr(resp, 'text', '') or '')
    if not isinstance(parsed, dict):
        return {
            'configured': True,
            'error': 'The AI reply could not be parsed as JSON.',
            'raw': (getattr(resp, 'text', '') or '')[:600],
            'recommendations': [],
        }
    recs = [r for r in (parsed.get('recommendations') or []) if isinstance(r, dict)]
    return {
        'configured': True,
        'provider': getattr(provider, 'name', ''),
        'model': getattr(resp, 'model', '') or getattr(provider, 'model', ''),
        'summary': str(parsed.get('summary') or '')[:500],
        'recommendations': recs[:12],
        'tokens': getattr(resp, 'completion_tokens', 0) + getattr(resp, 'prompt_tokens', 0),
    }


def get_analysis(*, force: bool = False) -> dict[str, Any]:
    """Cached analysis for the dashboard. `force` re-runs the LLM."""
    if not force:
        cached = cache.get(_CACHE_KEY)
        if cached:
            return cached
    result = analyze()
    # Stamp + cache only successful or clearly-actionable results.
    from django.utils import timezone

    result['generated_at'] = timezone.now().isoformat()
    cache.set(_CACHE_KEY, result, _TTL)
    return result


def cached_analysis() -> dict[str, Any] | None:
    """Whatever's cached, without triggering an LLM call (for page GET)."""
    return cache.get(_CACHE_KEY)
