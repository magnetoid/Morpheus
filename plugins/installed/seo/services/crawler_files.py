"""Non-sitemap crawler-facing files: robots.txt, llms.txt, PWA manifest.

Also home to the AI-crawler catalogue + per-bot policy resolver, which
robots.txt uses to emit per-UA blocks.
"""
from __future__ import annotations

from urllib.parse import urljoin

from ._helpers import _seo_plugin, _site_base_url, site_settings


#: 2026 AI/answer-engine crawler catalogue. Each entry: (UA, label,
# behaviour). Default policy = "allow" for every retrieval bot — they
# drive AI Overviews / ChatGPT / Perplexity citations. Training-only
# bots default to "allow" too so the merchant opts out, not in.
AI_CRAWLERS = [
    # OpenAI
    ('GPTBot',           'OpenAI · ChatGPT training crawler',          'training'),
    ('OAI-SearchBot',    'OpenAI · ChatGPT Search retrieval',          'search'),
    ('ChatGPT-User',     'OpenAI · ChatGPT user-triggered fetch',      'user'),
    # Anthropic
    ('ClaudeBot',        'Anthropic · Claude training crawler',        'training'),
    ('Claude-User',      'Anthropic · Claude user-triggered fetch',    'user'),
    ('Claude-SearchBot', 'Anthropic · Claude search retrieval',        'search'),
    # Perplexity
    ('PerplexityBot',    'Perplexity · indexing crawler',              'search'),
    ('Perplexity-User',  'Perplexity · user-triggered fetch',          'user'),
    # Google
    ('Google-Extended',  'Google · Bard / Vertex AI training opt-out', 'training'),
    # Apple
    ('Applebot-Extended','Apple · Apple Intelligence training opt-out','training'),
    # Meta
    ('Meta-ExternalAgent','Meta · AI training crawler',                'training'),
    # ByteDance (TikTok)
    ('Bytespider',       'ByteDance · LLM training crawler',           'training'),
    # Amazon
    ('Amazonbot',        'Amazon · Alexa + AI fetcher',                'search'),
    # Common Crawl
    ('CCBot',            'Common Crawl · public web archive',          'training'),
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
    """
    base = _site_base_url()
    policy = get_ai_crawler_policy()  # {ua_lowercase: True=allow / False=block}

    # `ai_crawler_default_allow` decides what happens for AI bots the
    # merchant hasn't explicitly toggled. True (the default) = allow;
    # flip to False to opt-out aggressively (good for "stop training
    # crawlers, period" stores). Per-bot overrides still win.
    default_allow = True
    seo_plugin = _seo_plugin()
    if seo_plugin is not None:
        try:
            default_allow = bool(seo_plugin.get_config_value(
                'ai_crawler_default_allow', True,
            ))
        except Exception:  # noqa: BLE001
            pass

    common_disallow = [
        'Disallow: /admin/',
        'Disallow: /dashboard/',
        'Disallow: /auth/',
        'Disallow: /cart/',
        'Disallow: /checkout/',
    ]

    lines: list[str] = []

    # Per-bot blocks. Default comes from the panel toggle —
    # `policy.get(...)` only returns the merchant's explicit choice;
    # use `default_allow` for everything else.
    for ua, _label, _kind in AI_CRAWLERS:
        allowed = policy.get(ua.lower(), default_allow)
        lines.append(f'User-agent: {ua}')
        if allowed:
            lines.append('Allow: /')
            lines.extend(common_disallow)
        else:
            lines.append('Disallow: /')
        lines.append('')

    # Universal fallback for every other crawler (Googlebot, Bingbot, …).
    lines.extend([
        'User-agent: *',
        'Allow: /',
        *common_disallow,
        '',
        f'Sitemap: {urljoin(base, "/sitemap.xml")}',
        f'Sitemap: {urljoin(base, "/sitemap-images.xml")}',
    ])
    return '\n'.join(lines).rstrip() + '\n'


def render_llms_txt(*, full: bool = False) -> str:
    """Generate /llms.txt (compact) or /llms-full.txt (with product summaries).

    Format follows the emerging llmstxt.org convention:
        # Site name
        > Short summary
        ## Section
        - [Title](url): description
    """
    s = site_settings()
    base = _site_base_url()
    name = s.organization_name or 'Morpheus store'
    out = [f'# {name}', '']
    if s.llms_txt_intro:
        out.extend(['> ' + s.llms_txt_intro.strip(), ''])
    else:
        out.extend([f'> {name} — visit {base} to browse.', ''])

    out.extend(['## Site map', f'- [Home]({base}/)',
                f'- [All products]({base}/products/)',
                f'- [Categories]({base}/categories/)',
                f'- [Search]({base}/search/?q=)',
                f'- [Sitemap XML]({base}/sitemap.xml)', ''])

    # Read the two new knobs once for the whole render.
    include_price = True
    include_stock = False
    seo_plugin = _seo_plugin()
    if seo_plugin is not None:
        try:
            include_price = bool(seo_plugin.get_config_value(
                'include_pricing_in_llms_txt', True,
            ))
            include_stock = bool(seo_plugin.get_config_value(
                'include_inventory_in_llms_txt', False,
            ))
        except Exception:  # noqa: BLE001
            pass

    try:
        from plugins.installed.catalog.models import Category, Product
        out.append('## Categories')
        for c in Category.objects.filter(parent__isnull=True).order_by('name')[:50]:
            out.append(f'- [{c.name}]({base}/products/?category={c.slug})')
        out.append('')

        out.append('## Products')
        qs = Product.objects.filter(status='active').order_by('-created_at')
        limit = 200 if full else 50
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
                    qty = sum(
                        s.quantity for s in
                        StockLevel.objects.filter(variant__product=p)
                    )
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
    return '\n'.join(out) + '\n'

# NOTE: the Web App Manifest moved to the dedicated `pwa` plugin
# (plugins/installed/pwa) which also ships a service worker + offline
# page + real icons. The old render_pwa_manifest() here pointed at
# icon files that 404'd and had no SW, so it was never installable.
