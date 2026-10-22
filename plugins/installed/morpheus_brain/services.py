import logging

from django.utils import timezone

from plugins.installed.morpheus_brain.models import BrainBriefing

logger = logging.getLogger('morpheus.brain.reports')


# ── AI advisory briefing ────────────────────────────────────────────────────
# A single long-form narrative the configured AI writes from the live platform
# signals (the same ones the structured analysis reads). Lives in this plugin —
# NOT core/brain — because it owns the BrainBriefing model; core must not import
# plugin models (enforced by scripts/check_core_boundary.py).

_BRIEFING_SYSTEM = (
    'You are Morpheus Brain — the resident principal engineer and strategic '
    'advisor for a modular Django e-commerce platform (Morpheus OS, storefront '
    'brand "dot books"). You are given real, current signals about the running '
    'system: plugin health, recent errors, code-quality findings, SEO/content '
    'audit, and storefront performance. Write a COMPREHENSIVE, candid advisory '
    'briefing — a holistic read on the state of the website and what to do next: '
    'what is healthy, what is at risk, concrete improvements, patches and changes '
    'to make, and any notable opportunities or observations. Ground every claim '
    'in the signals; prefer fixing real errors and code findings over speculation, '
    'but do surface strategic opportunities (performance, security, accessibility, '
    'SEO, conversion, DX) when the data supports them. Be specific and concrete — '
    'no filler, no vague platitudes.\n\n'
    'FORMAT: Markdown using only `## ` and `### ` headings and concise prose '
    'paragraphs (NO bullet lists or tables — they will not render). Open with a '
    '1-2 sentence state-of-the-system paragraph, then sections such as "## What '
    'is healthy", "## What needs attention", "## Recommended changes & patches", '
    '"## Opportunities". Aim for a substantial, readable briefing a CTO would scan.'
)


def _derive_title(text: str) -> str:
    """First heading line → title; else a dated default."""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('#'):
            t = s.lstrip('#').strip()
            if t:
                return t[:200]
    return f'Platform advisory — {timezone.now():%B %d, %Y}'


def _derive_summary(text: str) -> str:
    """First non-heading, non-empty paragraph → short scannable lead."""
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith('#'):
            return s[:500]
    return ''


def generate_briefing() -> dict:
    """Generate + persist a long-form AI advisory briefing. Returns a small
    status dict: {'configured': bool, 'briefing'|'error'|'message': ...}."""
    from core.agents.llm import LLMMessage, get_llm_provider
    from core.brain.signals import gather_all

    provider = get_llm_provider()
    if getattr(provider, 'name', '') in ('unconfigured', 'mock', 'base'):
        return {
            'configured': False,
            'message': 'No AI provider is configured — set one in Settings → AI to enable briefings.',
        }

    signals = gather_all()
    try:
        from core.brain.analyst import _summarize_signals

        digest = _summarize_signals(signals)
    except Exception:  # noqa: BLE001 — fall back to a trimmed raw dump
        import json

        digest = json.dumps(signals, default=str)[:6000]

    try:
        resp = provider.respond(
            messages=[
                LLMMessage(role='system', content=_BRIEFING_SYSTEM),
                LLMMessage(
                    role='user',
                    content=f'Platform signals:\n{digest}\n\nWrite the advisory briefing now.',
                ),
            ],
            temperature=0.5,
            max_tokens=3000,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning('briefing generation failed: %s', e, exc_info=True)
        return {'configured': True, 'error': str(e)[:300]}

    text = (getattr(resp, 'text', '') or '').strip()
    if not text:
        return {'configured': True, 'error': 'The AI returned an empty briefing.'}

    model = getattr(resp, 'model', '')
    briefing = BrainBriefing.objects.create(
        title=_derive_title(text),
        summary=_derive_summary(text),
        content=text,
        generated_by=f'{getattr(provider, "name", "")}{f" · {model}" if model else ""}',
        tokens_used=(getattr(resp, 'completion_tokens', 0) or 0)
        + (getattr(resp, 'prompt_tokens', 0) or 0),
    )

    # Keep only the most recent 20 briefings — the tab shows the latest; older
    # rows are history, not unbounded growth.
    old_ids = list(
        BrainBriefing.objects.order_by('-generated_at').values_list('id', flat=True)[20:]
    )
    if old_ids:
        BrainBriefing.objects.filter(id__in=old_ids).delete()

    logger.info('advisory briefing generated (%s tokens)', briefing.tokens_used)
    return {'configured': True, 'briefing': briefing}
