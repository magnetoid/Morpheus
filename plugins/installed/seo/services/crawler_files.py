"""Non-sitemap crawler-facing files: robots.txt, llms.txt, PWA manifest.

Also home to the AI-crawler catalogue + per-bot policy resolver, which
robots.txt uses to emit per-UA blocks.
"""

# ruff: noqa: PLC0415, I001, SIM105, S110
# Inline imports keep the catalog/inventory plugins soft (robots.txt +
# llms.txt must render even when they're disabled); the broad try/pass
# guards deliberately swallow config/DB misses so a crawler file never
# 500s. Same convention as services/jsonld.py.

from __future__ import annotations

import logging
from urllib.parse import urljoin

from ._helpers import _seo_plugin, _site_base_url, site_settings

logger = logging.getLogger('morpheus.seo')


#: 2026 AI/answer-engine crawler catalogue. Each entry: (UA, label,
# behaviour). Default policy = "allow" for every retrieval bot — they
# drive AI Overviews / ChatGPT / Perplexity citations. Training-only
# bots default to "allow" too so the merchant opts out, not in.
AI_CRAWLERS = [
    # OpenAI
    ('GPTBot', 'OpenAI · ChatGPT training crawler', 'training'),
    ('OAI-SearchBot', 'OpenAI · ChatGPT Search retrieval', 'search'),
    ('ChatGPT-User', 'OpenAI · ChatGPT user-triggered fetch', 'user'),
    # Anthropic
    ('ClaudeBot', 'Anthropic · Claude training crawler', 'training'),
    ('Claude-User', 'Anthropic · Claude user-triggered fetch', 'user'),
    ('Claude-SearchBot', 'Anthropic · Claude search retrieval', 'search'),
    # Perplexity
    ('PerplexityBot', 'Perplexity · indexing crawler', 'search'),
    ('Perplexity-User', 'Perplexity · user-triggered fetch', 'user'),
    # Google
    ('Google-Extended', 'Google · Bard / Vertex AI training opt-out', 'training'),
    # Apple
    ('Applebot-Extended', 'Apple · Apple Intelligence training opt-out', 'training'),
    # Meta
    ('Meta-ExternalAgent', 'Meta · AI training crawler', 'training'),
    # ByteDance (TikTok)
    ('Bytespider', 'ByteDance · LLM training crawler', 'training'),
    # Amazon
    ('Amazonbot', 'Amazon · Alexa + AI fetcher', 'search'),
    # Cohere
    ('cohere-ai', 'Cohere · RAG / grounding fetcher', 'search'),
    # Common Crawl
    ('CCBot', 'Common Crawl · public web archive', 'training'),
]


def get_ai_crawler_policy() -> dict[str, bool]:
    """Read per-bot allow/disallow policy from seo plugin config.

    Default = all-allow. Stored as ``{ua_lowercase: bool}`` in the plugin
    config JSON. Returns the merged map ready for robots.txt emission.
    """
    seo_plugin = _seo_plugin()
    if seo_plugin is None:
        return {}
    try:
        raw = seo_plugin.get_config_value('ai_crawler_policy', {}) or {}
        if not isinstance(raw, dict):
            return {}
        return {k.lower(): bool(v) for k, v in raw.items()}
    except Exception:  # noqa: BLE001 — never break robots.txt over a config miss
        return {}


def render_robots_txt() -> str:
    """robots.txt with explicit AI-crawler blocks.

    A 2026 storefront wants per-bot control: opt out of LLM training
    crawlers without blocking the retrieval bots that drive AI Overviews
    + ChatGPT/Perplexity citations. Order matters — specific UAs first,
    then the universal ``User-agent: *`` fallback.

    *Which* paths are blocked is no longer decided here: `_robots_document()`
    fires `SEO_ROBOTS_RULES` and each app contributes the URLs it owns.
    """
    policy = get_ai_crawler_policy()  # {ua_lowercase: True=allow / False=block}

    # `ai_crawler_default_allow` decides what happens for AI bots the
    # merchant hasn't explicitly toggled. True (the default) = allow;
    # flip to False to opt-out aggressively (good for "stop training
    # crawlers, period" stores). Per-bot overrides still win.
    default_allow = True
    seo_plugin = _seo_plugin()
    if seo_plugin is not None:
        try:
            default_allow = bool(
                seo_plugin.get_config_value(
                    'ai_crawler_default_allow',
                    True,
                )
            )
        except Exception:  # noqa: BLE001
            pass

    doc = _robots_document()
    common_disallow = [f'Disallow: {path}' for path in doc.disallowed]
    common_allow = [f'Allow: {path}' for path in doc.allowed]

    lines: list[str] = []

    # Per-bot blocks. Default comes from the panel toggle —
    # `policy.get(...)` only returns the merchant's explicit choice;
    # use `default_allow` for everything else.
    for ua, _label, _kind in AI_CRAWLERS:
        allowed = policy.get(ua.lower(), default_allow)
        lines.append(f'User-agent: {ua}')
        if allowed:
            lines.append('Allow: /')
            lines.extend(common_allow)
            lines.extend(common_disallow)
        else:
            lines.append('Disallow: /')
        lines.append('')

    # Universal fallback for every other crawler (Googlebot, Bingbot, …).
    lines.extend(
        [
            'User-agent: *',
            'Allow: /',
            *common_allow,
            *common_disallow,
            '',
        ]
    )
    # A store hidden until launch names no sitemap; crawling stays allowed so
    # its pages' noindex is read (a Disallow would freeze indexed URLs).
    from plugins.installed.seo.services.launch import hidden_until_launch

    if not hidden_until_launch():
        lines.extend(f'Sitemap: {url}' for url in doc.sitemaps)

    return '\n'.join(lines).rstrip() + '\n'


def _robots_document():
    """Seed the document with what seo owns, then let the owners answer.

    seo seeds only the two paths that belong to no plugin (`/admin/` and
    `/dashboard/` are chrome) plus its own sitemaps and the parameters its
    index rules mark unfetchable. `/cart/`, `/checkout/`, `/auth/` used to be
    hardcoded here — four URL shapes belonging to `storefront`, which meant a
    merchant who moved checkout, or a plugin adding a private surface of its
    own, had no way to say so except by editing this file.
    """
    from core.robots import RobotsDocument
    from morpheus.core import MorpheusEvents, hook_registry

    doc = RobotsDocument()
    doc.disallow('/admin/')
    doc.disallow('/dashboard/')

    # Parameters a merchant policied `block`: the only index rule that saves
    # crawl budget, because it stops the fetch instead of labelling the result.
    try:
        from plugins.installed.seo.rules import blocked_param_patterns

        for pattern in blocked_param_patterns():
            doc.disallow(pattern)
    except Exception:  # noqa: BLE001 — an unmigrated table must not empty robots.txt
        logger.debug('seo: index rules unavailable for robots.txt', exc_info=True)

    base = _site_base_url()
    # Single sitemap-index entry — a discovery doc listing every sub-sitemap
    # (main, images, news). Crawlers prefer the index over a flat per-file list.
    doc.sitemap(urljoin(base, '/sitemap-index.xml'))
    # Google News specifically looks for a dedicated `Sitemap: …-news.xml` line.
    seo_plugin = _seo_plugin()
    if seo_plugin is not None:
        try:
            if seo_plugin.get_config_value('news_sitemap_enabled', False):
                doc.sitemap(urljoin(base, '/sitemap-news.xml'))
        except Exception:  # noqa: BLE001
            pass

    try:
        return hook_registry.filter(MorpheusEvents.SEO_ROBOTS_RULES, doc) or doc
    except Exception:  # noqa: BLE001 — a broken subscriber costs its lines, not the file
        logger.warning('seo: SEO_ROBOTS_RULES contribution failed', exc_info=True)
        return doc


def render_llms_txt(*, full: bool = False) -> str:  # noqa: PLR0912, PLR0915 — linear llms.txt section builder
    """Generate /llms.txt (compact) or /llms-full.txt (with product summaries).

    Format follows the emerging llmstxt.org convention:
        # Site name
        > Short summary
        ## Section
        - [Title](url): description
    """
    s = site_settings()
    # rstrip is load-bearing: `_site_base_url()` ends in '/', and every line
    # below interpolates f'{base}/...', so the live file shipped 45 urls like
    # `https://example.com//journal/x/`. They resolve, but llms.txt exists to be
    # read by machines. `render_agents_md` had the rstrip; this never did.
    base = _site_base_url().rstrip('/')
    name = s.organization_name or 'Morpheus store'
    out = [f'# {name}', '']
    if s.llms_txt_intro:
        out.extend(['> ' + s.llms_txt_intro.strip(), ''])
    else:
        out.extend([f'> {name} — visit {base} to browse.', ''])

    out.extend(
        [
            '## Site map',
            f'- [Home]({base}/)',
            f'- [All products]({base}/products/)',
            f'- [Search]({base}/search/?q=)',
            f'- [Sitemap XML]({base}/sitemap.xml)',
            '',
        ]
    )

    # Read the two new knobs once for the whole render.
    include_price = True
    include_stock = False
    seo_plugin = _seo_plugin()
    if seo_plugin is not None:
        try:
            include_price = bool(
                seo_plugin.get_config_value(
                    'include_pricing_in_llms_txt',
                    True,
                )
            )
            include_stock = bool(
                seo_plugin.get_config_value(
                    'include_inventory_in_llms_txt',
                    False,
                )
            )
        except Exception:  # noqa: BLE001
            pass

    try:
        from plugins.installed.catalog.models import Category, Product

        out.append('## Categories')
        for c in Category.objects.filter(parent__isnull=True).order_by('name')[:50]:
            out.append(f'- [{c.name}]({base}/category/{c.slug}/)')
        out.append('')

        qs = Product.objects.filter(status='active').order_by('-created_at')
        limit = 200 if full else 50
        # A heading with no rows under it is worse than no heading: it tells a
        # crawler the shop has no catalogue. Only open the section once a row
        # exists — a vertical whose products live elsewhere contributes its own
        # through SEO_LLMS_SECTIONS below.
        if qs.exists():
            out.append('## Products')
        for p in qs[:limit]:
            # Per-product markdown export — let crawlers fetch the
            # canonical content without parsing HTML. /md/products/<slug>
            md_url = f'{base}/md/products/{p.slug}'
            line = f'- [{p.name}]({base}/products/{p.slug}/) ({md_url})'

            # Optional pricing — improves AI citation accuracy in
            # ChatGPT / Perplexity / AI Overviews when they answer
            # "how much is X" queries.
            if include_price and p.price:
                line += f' — {p.price.amount} {p.price.currency}'

            # Optional stock signal — off by default because
            # inventory churns fast and stale LLM caches embarrass.
            if include_stock:
                try:
                    from plugins.installed.inventory.models import StockLevel

                    qty = sum(s.quantity for s in StockLevel.objects.filter(variant__product=p))
                    line += f' — {"In stock" if qty > 0 else "Out of stock"}'
                except Exception:  # noqa: BLE001
                    pass

            if full:
                desc = (p.short_description or p.description or '')[:160]
                if desc:
                    line += f': {desc}'
            out.append(line)
    except Exception:  # noqa: BLE001
        pass

    # Journal / editorial — the content answer engines most want to cite.
    # Read the same published cms.Page journal entries the sitemaps use.
    try:
        from plugins.installed.cms.services import list_journal_entries

        entries = list_journal_entries(limit=200 if full else 50)
        if entries:
            out.append('')
            out.append('## Journal')
            for e in entries:
                slug = e.get('slug', '')
                line = f'- [{e.get("title", "")}]({base}/journal/{slug}/)'
                if full:
                    summary = (e.get('excerpt') or '')[:160]
                    if summary:
                        line += f': {summary}'
                out.append(line)
    except Exception:  # noqa: BLE001
        pass

    out.extend(_contributed_llms_sections(base=base, full=full))
    return '\n'.join(out) + '\n'


def _contributed_llms_sections(*, base: str, full: bool) -> list[str]:
    """`SEO_LLMS_SECTIONS` subscribers append their own catalogue sections.

    Fail-soft per the hook bus: a broken subscriber must not take llms.txt down,
    because the file is fetched by crawlers, not by a person who would report it.
    """
    from morpheus.core import MorpheusEvents, hook_registry

    try:
        sections = hook_registry.filter(MorpheusEvents.SEO_LLMS_SECTIONS, [], base=base, full=full)
    except Exception:  # noqa: BLE001
        return []
    lines: list[str] = []
    for section in sections or []:
        title = str((section or {}).get('title') or '').strip()
        rows = [str(r) for r in ((section or {}).get('lines') or []) if str(r).strip()]
        if not title or not rows:
            continue
        lines.extend(['', f'## {title}', *rows])
    return lines


def render_agents_md() -> str:
    """Generate /agents.md — the agent-onboarding manifest.

    A Markdown page that tells autonomous shopping agents what this store is,
    how to *discover* it (llms.txt / feed / sitemap — seo's own surfaces, seeded
    here), and how to *transact* with it. The transaction surfaces (MCP / UCP /
    well-known manifests + auth) are owned by other plugins, so they are pulled
    in through the AGENT_READINESS_SECTIONS filter — a disabled owner's section
    simply never appears, so /agents.md never advertises an endpoint that isn't
    live. See docs/AGENT_PROTOCOLS.md.
    """
    s = site_settings()
    base = _site_base_url().rstrip('/')
    name = s.organization_name or 'Morpheus store'

    out = [f'# {name} — for AI agents', '']
    intro = (s.llms_txt_intro or '').strip()
    if intro:
        out.extend(['> ' + intro, ''])
    out.extend(
        [
            'This page tells autonomous agents how to discover and transact with '
            'this store. Content is generated from the live catalog and policies.',
            '',
            '## Discovery',
            f'- Catalog for LLMs: {base}/llms.txt (full: {base}/llms-full.txt)',
            f'- Structured product feed: {base}/ai/products.json',
            f'- Per-product markdown: {base}/md/products/<slug>',
            f'- Sitemap: {base}/sitemap.xml',
            f'- Browse: {base}/products/',
            '',
        ]
    )

    # Owner-contributed sections (agent endpoints, policies). Each subscriber
    # appends {'heading', 'body', 'priority'}; a disabled owner contributes
    # nothing (the bus skips inactive plugins).
    sections: list[dict] = []
    try:
        from morpheus.core import MorpheusEvents, hook_registry

        result = hook_registry.filter(MorpheusEvents.AGENT_READINESS_SECTIONS, value=[])
        if isinstance(result, list):
            sections = [x for x in result if isinstance(x, dict) and x.get('heading')]
    except Exception:  # noqa: BLE001 — a bad subscriber must not break the file.
        sections = []

    for sec in sorted(sections, key=lambda d: d.get('priority', 100)):
        body = str(sec.get('body', '')).strip()
        out.append(f'## {sec["heading"]}')
        if body:
            out.extend(['', body])
        out.append('')

    out.extend(['## About', f'Generated by Morpheus for {base}. Machine-readable by design.'])
    return '\n'.join(out) + '\n'


# NOTE: the Web App Manifest moved to the dedicated `pwa` plugin
# (plugins/installed/pwa) which also ships a service worker + offline
# page + real icons. The old render_pwa_manifest() here pointed at
# icon files that 404'd and had no SW, so it was never installable.
