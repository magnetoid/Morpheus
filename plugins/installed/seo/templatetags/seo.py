"""
Template tags for the SEO plugin.

Usage:

    {% load seo %}
    <head>
      ...
      {% seo_meta object=product fallback_title="dot books." fallback_description="A quieter shelf for louder books." %}
    </head>

The tag emits <title>, meta description, OG, Twitter Card, canonical link,
robots, keywords, and a JSON-LD <script>.
"""
from __future__ import annotations

from django import template
from django.utils.safestring import mark_safe

from plugins.installed.seo.services import resolve_meta

register = template.Library()


def _canonical_from_request(request) -> tuple[str, bool]:
    """Build the canonical URL from a request, stripping query params that
    `SiteSeoSettings.noindex_query_params` marks as duplicate-content
    generators (page, sort, ref, gclid, …).

    Returns ``(canonical_url, had_noindex_param)``. The flag lets the
    caller bump robots to ``noindex, follow`` so faceted SERPs don't
    dilute ranking signals.
    """
    from urllib.parse import urlencode, urlsplit, urlunsplit
    if request is None:
        return '', False
    try:
        absolute = request.build_absolute_uri()
    except Exception:  # noqa: BLE001
        return '', False

    try:
        from plugins.installed.seo.services import site_settings
        blocklist = set(site_settings().noindex_query_params or [])
    except Exception:  # noqa: BLE001 — settings may not be migrated yet
        blocklist = set()
    if not blocklist:
        return absolute, False

    parts = urlsplit(absolute)
    if not parts.query:
        return absolute, False

    from urllib.parse import parse_qsl
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    had_blocked = any(k in blocklist for k, _ in pairs)
    kept = [(k, v) for k, v in pairs if k not in blocklist]
    rebuilt = urlunsplit(parts._replace(query=urlencode(kept)))
    return rebuilt, had_blocked


@register.simple_tag(takes_context=True)
def seo_meta(
    context,
    object=None,
    fallback_title: str = '',
    fallback_description: str = '',
    fallback_image: str = '',
    canonical_url: str = '',
    og_type: str = 'website',
):
    request = context.get('request')
    had_noindex_qp = False
    if not canonical_url:
        canonical_url, had_noindex_qp = _canonical_from_request(request)

    meta = resolve_meta(
        obj=object,
        fallback_title=fallback_title,
        fallback_description=fallback_description,
        fallback_image=fallback_image,
        canonical_url=canonical_url,
        og_type=og_type,
    )
    if had_noindex_qp and 'noindex' not in meta.robots:
        # Faceted/paginated SERPs: keep crawl signal (follow) but stop
        # indexing the duplicate URL.
        meta.robots = 'noindex, follow'
    return mark_safe(meta.to_html())


@register.simple_tag
def seo_organization_jsonld():
    """Emit <script type="application/ld+json"> for the Organization."""
    from plugins.installed.seo.services import organization_jsonld, _jsonld_dump
    obj = organization_jsonld()
    if not obj:
        return ''
    return mark_safe(f'<script type="application/ld+json">{_jsonld_dump(obj)}</script>')


@register.simple_tag
def seo_website_jsonld():
    """Emit <script type="application/ld+json"> for the WebSite (sitelinks search)."""
    from plugins.installed.seo.services import website_jsonld, _jsonld_dump
    obj = website_jsonld()
    if not obj:
        return ''
    return mark_safe(f'<script type="application/ld+json">{_jsonld_dump(obj)}</script>')


@register.simple_tag
def seo_product_jsonld(product):
    """Emit Product JSON-LD with offer / availability / aggregateRating."""
    if product is None:
        return ''
    from plugins.installed.seo.services import product_jsonld, _jsonld_dump
    return mark_safe(f'<script type="application/ld+json">{_jsonld_dump(product_jsonld(product))}</script>')


@register.simple_tag
def seo_breadcrumb_jsonld(items):
    """Emit BreadcrumbList JSON-LD. `items` is a list of {name, url}."""
    if not items:
        return ''
    from plugins.installed.seo.services import breadcrumb_jsonld, _jsonld_dump
    return mark_safe(f'<script type="application/ld+json">{_jsonld_dump(breadcrumb_jsonld(items))}</script>')


@register.simple_tag
def seo_verification_metas():
    """Emit any configured Google / Bing / Pinterest / FB verification metas."""
    from plugins.installed.seo.services import site_settings
    s = site_settings()
    out = []
    pairs = [
        ('google-site-verification', s.google_site_verification),
        ('msvalidate.01', s.bing_verification),
        ('p:domain_verify', s.pinterest_verification),
        ('facebook-domain-verification', s.facebook_domain_verification),
    ]
    for name, content in pairs:
        if content:
            out.append(f'<meta name="{name}" content="{content}">')
    return mark_safe('\n'.join(out))


@register.simple_tag(takes_context=True)
def seo_pagination_links(context, page_obj=None):
    """Emit <link rel="prev"> + <link rel="next"> for a Django Paginator
    page. Improves crawl efficiency for paginated PLPs.

    Pass a `page_obj` that exposes `.has_previous`, `.has_next`,
    `.previous_page_number`, `.next_page_number`. No-op if either is
    absent or there's only one page.
    """
    if page_obj is None:
        return ''
    request = context.get('request')
    if request is None:
        return ''
    from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
    try:
        parts = urlsplit(request.build_absolute_uri())
    except Exception:  # noqa: BLE001
        return ''
    base_pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != 'page']

    def _link_for(page_num: int) -> str:
        pairs = list(base_pairs) + [('page', str(page_num))]
        href = urlunsplit(parts._replace(query=urlencode(pairs)))
        return href

    out = []
    if getattr(page_obj, 'has_previous', lambda: False)():
        out.append(f'<link rel="prev" href="{_link_for(page_obj.previous_page_number())}">')
    if getattr(page_obj, 'has_next', lambda: False)():
        out.append(f'<link rel="next" href="{_link_for(page_obj.next_page_number())}">')
    return mark_safe('\n'.join(out))


@register.simple_tag
def seo_llms_link():
    """Emit a <link rel="alternate"> hint to /llms.txt for LLM crawlers."""
    from plugins.installed.seo.services import site_settings
    s = site_settings()
    if not s.llms_txt_enabled:
        return ''
    return mark_safe('<link rel="alternate" type="text/plain" href="/llms.txt" title="LLM-friendly site map">')
