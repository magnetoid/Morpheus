import logging

from django.utils import timezone

from plugins.installed.morpheus_brain.models import BrainBriefing, DailyReport, ReportReference

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


def generate_daily_reports():
    """
    Automated generation of daily reports based on deep web research of 2026/2027 trends.
    This would normally be hooked up to an LLM chain or Celery task.
    For demonstration/seed purposes, we will generate the structured findings from our
    comprehensive 2027 web research here.
    """

    # Check if reports for today already exist
    if DailyReport.objects.filter(published_at__date=timezone.now().date()).exists():
        logger.info('Daily reports already generated for today.')
        return

    # 1. Code Optimization Report
    report1 = DailyReport.objects.create(
        title='The Shift to Wasm & Agentic IDEs in 2027',
        category='code_opt',
        summary='WebAssembly and Agentic IDEs are replacing traditional JS bottlenecks and rule-based navigation.',
        content=(
            '### WebAssembly (Wasm) Integration\n'
            'By 2027, WebAssembly is significantly enhancing JavaScript application performance by allowing C++ '
            'and Rust to run at near-native speeds in the browser. This eliminates the traditional JS performance '
            'bottlenecks for heavy dashboards and real-time data visualizers.\n\n'
            '### Agentic IDEs\n'
            "IDE assistants have evolved from autocomplete tools into 'Teammates' (Agentic IDEs). They now "
            "run tests, fix bugs, and refactor across entire codebases autonomously. 'Prompt Engineering' is being "
            "replaced by 'Constraint Engineering' (defining testable rules like `max_bundle_size: 200kb`)."
        ),
    )
    ReportReference.objects.create(
        report=report1,
        title="JavaScript's 2027 Evolution: Are Devs Ready?",
        url='https://codeandcoffe.com/javascript-s-2027-evolution-are-devs-ready/',
    )
    ReportReference.objects.create(
        report=report1,
        title='10 Predictions for AI Coding in 2027',
        url='https://markaicode.com/ai-coding-predictions-2027',
    )

    # 2. Feature Enhancements Report
    report2 = DailyReport.objects.create(
        title='Zero-UI, Calm Design, & Hyper-Personalization',
        category='feat_enh',
        summary='Interfaces are becoming invisible, calm, and adapt dynamically to individual users.',
        content=(
            '### Zero UI & Biophilic Design\n'
            'Automation overload is real. In 2027, interfaces must show orientation and intent without overwhelming the user. '
            "'Zero UI' means the system gracefully disappears, utilizing voice, gestures, and ambient intelligence. "
            "Visual design is adopting 'Calm' and 'Biophilic' patterns to reduce cognitive fatigue.\n\n"
            '### Adaptive UI\n'
            'One size no longer fits all. UIs are now adapting to persona, behavior, and context in real-time. '
            'A new user receives a guided wizard, while a power user sees advanced data visualizations.'
        ),
    )
    ReportReference.objects.create(
        report=report2,
        title='Top 20 Biggest UI/UX Design Trends to Watch in 2026/2027',
        url='https://crediblesoft.com/top-20-biggest-ui-ux-design-trends-to-watch',
    )
    ReportReference.objects.create(
        report=report2,
        title='Web Design Trends 2026: Fluid, Calm, Human-Centered Experiences',
        url='https://tentackles.com/blog/web-design-trends-2026',
    )

    # 3. E-commerce Advancements Report
    report3 = DailyReport.objects.create(
        title='Agentic Commerce & The Autonomous Buyer',
        category='ecom_adv',
        summary='AI Agents are replacing traditional search-and-click shopping, executing purchases on behalf of users.',
        content=(
            '### The Rise of Agentic Commerce\n'
            'By 2027-2030, agentic commerce is projected to account for 15-25% of all online sales ($500B in the US alone). '
            "Consumers are delegating research, comparison, and checkout to autonomous AI agents. The 'Search Bar' is being "
            "replaced by 'Answer Engines'.\n\n"
            '### Machine-Readable Catalogs\n'
            'Brands must shift from SEO to AEO (Answer Engine Optimization) and GEO (Generative Engine Optimization). '
            'If product data is not highly structured and machine-readable via protocols like ACP (Agentic Commerce Protocol) '
            'or UCP, the brand becomes invisible to the AI agents making the purchasing decisions.'
        ),
    )
    ReportReference.objects.create(
        report=report3,
        title='Agentic Commerce Trends 2026–2030: The Rise of the Autonomous Economy',
        url='https://emerline.com/blog/agentic-commerce-trends',
    )
    ReportReference.objects.create(
        report=report3,
        title='The Rise of AI Shopping Agents: How Product Discovery Will Work in 2027',
        url='https://surferstack.com/guides/the-rise-of-ai-shopping-agents-how-product-discovery-will-work-in-2027-2030',
    )

    logger.info('Daily reports successfully generated.')
