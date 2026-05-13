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
from django.utils.html import escape
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
def seo_product_md_link(slug):
    """<link rel="alternate" type="text/markdown" …> pointing at the
    LLM-friendly markdown view of this product. Used by ChatGPT /
    Perplexity / Claude crawlers as the canonical text source."""
    if not slug:
        return ''
    href = f'/md/products/{slug}'
    return mark_safe(f'<link rel="alternate" type="text/markdown" href="{href}" title="Plain-text product description for LLM crawlers">')


@register.simple_tag
def seo_product_og(product):
    """Open Graph product extensions + Twitter label/data pairs.

    Renders the product:* OG fields (price.amount, price.currency,
    availability, condition) so link previews in Slack / iMessage /
    Discord / ChatGPT show price + availability inline. Also emits
    Twitter Card label1/data1/label2/data2 with the same info.

    Accepts GraphQL dict OR Django model — same shape resolver as
    seo_product_jsonld."""
    if product is None:
        return ''

    def g(name, default=None):
        if isinstance(product, dict):
            return product.get(name, default)
        return getattr(product, name, default)

    price = g('price')
    amount = currency = ''
    if price is not None:
        if isinstance(price, dict):
            amount, currency = str(price.get('amount', '')), str(price.get('currency', ''))
        else:
            amount, currency = str(getattr(price, 'amount', price)), str(getattr(price, 'currency', ''))
    avail = 'in stock'
    out = [
        '<meta property="og:type" content="product">',
        f'<meta property="product:price:amount" content="{amount}">',
        f'<meta property="product:price:currency" content="{currency}">',
        f'<meta property="product:availability" content="{avail}">',
        '<meta property="product:condition" content="new">',
        '<meta name="twitter:label1" content="Price">',
        f'<meta name="twitter:data1" content="{amount} {currency}">',
        '<meta name="twitter:label2" content="Availability">',
        f'<meta name="twitter:data2" content="{avail}">',
    ]
    return mark_safe('\n'.join(out))


@register.simple_tag
def seo_speakable_jsonld(selectors=None):
    """Speakable schema — declares which CSS selectors hold spoken
    content for Google Assistant / Siri / Alexa voice reading."""
    from plugins.installed.seo.services import speakable_jsonld, _jsonld_dump
    obj = speakable_jsonld(list(selectors) if selectors else None)
    return mark_safe(f'<script type="application/ld+json">{_jsonld_dump(obj)}</script>')


@register.simple_tag
def seo_faq_jsonld(items):
    """FAQ schema — items is a list of {q, a}. Although Google retired
    FAQ rich snippets in May 2026, AI engines still use the schema for
    citation when the merchant publishes Q&A content."""
    if not items:
        return ''
    from plugins.installed.seo.services import faq_jsonld, _jsonld_dump
    return mark_safe(f'<script type="application/ld+json">{_jsonld_dump(faq_jsonld(items))}</script>')


@register.simple_tag(takes_context=True)
def seo_collection_jsonld(context, items, name='', description=''):
    """Emit CollectionPage + ItemList JSON-LD for a PLP/category.
    `items` is a list of {name, url, image} (use camelCase or snake;
    the helper accepts both)."""
    if not items:
        return ''
    request = context.get('request')
    try:
        url = request.build_absolute_uri() if request else ''
    except Exception:  # noqa: BLE001
        url = ''
    normalised = []
    for it in items:
        if not it:
            continue
        normalised.append({
            'name': it.get('name') or it.get('title') or '',
            'url': it.get('url') or '',
            'image': it.get('image') or it.get('primaryImage', {}).get('url') if isinstance(it.get('primaryImage'), dict) else (it.get('image') or ''),
        })
    from plugins.installed.seo.services import collection_page_jsonld, _jsonld_dump
    obj = collection_page_jsonld(
        name=name or 'Collection',
        url=url,
        description=description,
        items=normalised,
    )
    return mark_safe(f'<script type="application/ld+json">{_jsonld_dump(obj)}</script>')


@register.simple_tag(takes_context=True)
def seo_qa_jsonld(context, qa, name=''):
    """QAPage schema — qa is a list of {q, a}."""
    if not qa:
        return ''
    request = context.get('request')
    try:
        url = request.build_absolute_uri() if request else ''
    except Exception:  # noqa: BLE001
        url = ''
    from plugins.installed.seo.services import qa_page_jsonld, _jsonld_dump
    obj = qa_page_jsonld(name=name or 'Q&A', url=url, qa=qa)
    return mark_safe(f'<script type="application/ld+json">{_jsonld_dump(obj)}</script>')


@register.simple_tag
def seo_responsive_image(src, alt='', sizes='', widths='400,800,1200',
                         priority=False, css_class='', style=''):
    """Emit a <picture> element with AVIF + WebP sources + a JPEG/PNG
    fallback `<img>`, generated via /img/<fmt>/<w>/... on demand.

    Args:
      src: absolute media URL (e.g. ``/media/products/foo.jpg``) or a
        Django FieldFile-like object with a ``.url`` attribute.
      alt: required alt text. Falls back to '' (mark decorative).
      sizes: CSS `sizes` attribute (e.g. "(min-width: 900px) 480px, 100vw").
      widths: comma-separated widths to emit; restricted to ALLOWED_IMAGE_WIDTHS.
      priority: when truthy, emits fetchpriority=high + loading=eager
        (use only for the LCP image).
      css_class / style: forwarded to the <img>.
    """
    # Normalise src to a /media/... path.
    url = src
    if hasattr(src, 'url'):
        try:
            url = src.url
        except Exception:  # noqa: BLE001
            return ''
    url = str(url or '')
    if not url:
        return ''
    # Strip absolute prefix; we only resize images under MEDIA_ROOT.
    if url.startswith('http://') or url.startswith('https://'):
        # Best-effort: keep the original URL; skip resize for off-site.
        loading = 'eager' if priority else 'lazy'
        fp = ' fetchpriority="high"' if priority else ''
        return mark_safe(
            f'<img src="{escape(url)}" alt="{escape(alt)}" '
            f'loading="{loading}" decoding="async"{fp} '
            f'{f"class={css_class!r}" if css_class else ""} '
            f'{f"style={style!r}" if style else ""}>'
        )
    media_prefix = '/media/'
    if not url.startswith(media_prefix):
        return mark_safe(f'<img src="{escape(url)}" alt="{escape(alt)}">')
    rel = url[len(media_prefix):]

    from plugins.installed.seo.services import ALLOWED_IMAGE_WIDTHS
    requested = []
    for w in str(widths).split(','):
        w = w.strip()
        if not w.isdigit():
            continue
        wi = int(w)
        if wi in ALLOWED_IMAGE_WIDTHS:
            requested.append(wi)
    if not requested:
        requested = [400, 800, 1200]

    def srcset_for(fmt: str) -> str:
        return ', '.join(f'/img/{fmt}/{w}/{rel} {w}w' for w in requested)

    fallback_w = max(requested)
    fallback = f'/img/webp/{fallback_w}/{rel}'
    loading = 'eager' if priority else 'lazy'
    fp = ' fetchpriority="high"' if priority else ''
    sizes_attr = f' sizes="{escape(sizes)}"' if sizes else ''
    class_attr = f' class="{escape(css_class)}"' if css_class else ''
    style_attr = f' style="{escape(style)}"' if style else ''

    return mark_safe(
        f'<picture>'
        f'<source type="image/avif" srcset="{escape(srcset_for("avif"))}"{sizes_attr}>'
        f'<source type="image/webp" srcset="{escape(srcset_for("webp"))}"{sizes_attr}>'
        f'<img src="{escape(fallback)}" alt="{escape(alt)}" '
        f'loading="{loading}" decoding="async"{fp}'
        f'{class_attr}{style_attr}>'
        f'</picture>'
    )


@register.simple_tag(takes_context=True)
def seo_article_jsonld(context, *, headline, body, author='', published=None,
                       modified=None, image=''):
    """Article schema for journal posts. AI engines weigh this heavily
    for citation (especially Person.author + datePublished + sameAs)."""
    request = context.get('request')
    try:
        url = request.build_absolute_uri() if request else ''
    except Exception:  # noqa: BLE001
        url = ''
    from plugins.installed.seo.services import article_jsonld, _jsonld_dump
    obj = article_jsonld(
        headline=headline or '', body=body or '', url=url,
        author=author or '', published_at=published, image=image,
    )
    if modified:
        try:
            obj['dateModified'] = modified.isoformat()
        except Exception:  # noqa: BLE001
            pass
    return mark_safe(f'<script type="application/ld+json">{_jsonld_dump(obj)}</script>')


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
