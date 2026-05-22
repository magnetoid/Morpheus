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
    """Build the canonical URL from a request, stripping query params.

    Two complementary strategies:
      1. PluginConfig['seo']['canonical_strip_query_params'] — when
         True, strip EVERY query param from the canonical (standard
         SEO hygiene; collapses utm_/fbclid/gclid into the clean URL).
      2. ``SiteSeoSettings.noindex_query_params`` — a per-key
         blocklist for cases where you want some params kept but
         signal duplicate-content noindex when the listed ones show
         up (e.g. ``?sort=price`` → noindex,follow).

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

    parts = urlsplit(absolute)
    if not parts.query:
        return absolute, False

    # Read both knobs defensively — never crash the page render.
    strip_all = True   # default ON (matches the PluginConfig default)
    blocklist: set[str] = set()
    try:
        from plugins.registry import plugin_registry
        seo_plugin = None
        for attr in ('get', 'get_plugin'):
            fn = getattr(plugin_registry, attr, None)
            if callable(fn):
                try:
                    seo_plugin = fn('seo')
                except Exception:  # noqa: BLE001
                    continue
                if seo_plugin is not None:
                    break
        if seo_plugin is not None:
            strip_all = bool(seo_plugin.get_config_value(
                'canonical_strip_query_params', True,
            ))
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.seo.services import site_settings
        blocklist = set(site_settings().noindex_query_params or [])
    except Exception:  # noqa: BLE001
        pass

    if strip_all:
        # Aggressive: drop EVERY query param from the canonical. Still
        # raises the noindex flag when one of the blocklisted params
        # was present so faceted views get noindex,follow.
        from urllib.parse import parse_qsl
        pairs = parse_qsl(parts.query, keep_blank_values=True)
        had_blocked = any(k in blocklist for k, _ in pairs) if blocklist else False
        rebuilt = urlunsplit(parts._replace(query=''))
        return rebuilt, had_blocked

    if not blocklist:
        return absolute, False

    from urllib.parse import parse_qsl
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    had_blocked = any(k in blocklist for k, _ in pairs)
    kept = [(k, v) for k, v in pairs if k not in blocklist]
    rebuilt = urlunsplit(parts._replace(query=urlencode(kept)))
    return rebuilt, had_blocked


@register.simple_tag
def seo_title(title: str, *, category: str = '', site_name: str = '') -> str:
    """Render the ``<title>`` text using SiteSeoSettings.title_template.

    Variables in the template:
      ``{title}``      — the page-specific title (passed in)
      ``{site_name}``  — falls back to SiteSeoSettings.organization_name
                          → core.StoreSettings.store_name → empty
      ``{category}``   — optional category name (e.g. on PDPs)

    Truncates the result to ``title_max_length`` (default 60) so we
    don't ship a 200-char string to Google. Falls back to a clean
    "title — site_name" when the template is malformed or the
    SiteSeoSettings row doesn't exist yet (fresh install).
    """
    title = (title or '').strip()
    category = (category or '').strip()
    site_name = (site_name or '').strip()

    # Resolve the site name + template + length cap. Defensive — never
    # crash the page render over an SEO formatting issue.
    template_str = '{title} — {site_name}'
    max_len = 60
    try:
        from plugins.installed.seo.services import site_settings
        s = site_settings()
        template_str = (s.title_template or template_str).strip()
        if s.title_max_length and int(s.title_max_length) > 0:
            max_len = int(s.title_max_length)
        if not site_name:
            site_name = (s.organization_name or '').strip()
    except Exception:  # noqa: BLE001
        pass

    if not site_name:
        # Last-resort: core.StoreSettings.store_name.
        try:
            from core.models import StoreSettings
            store = StoreSettings.objects.first()
            site_name = getattr(store, 'store_name', '') or ''
        except Exception:  # noqa: BLE001
            pass

    try:
        rendered = template_str.format(
            title=title or 'Untitled',
            site_name=site_name or '',
            category=category or '',
        )
    except (KeyError, IndexError, ValueError):
        # Malformed template (unknown placeholder, stray brace). Fall
        # back to a safe shape instead of raising.
        rendered = f'{title} — {site_name}' if site_name else title

    # Collapse the common "Title —  " orphan when site_name is empty
    # AND the template ended with " — {site_name}".
    rendered = rendered.replace(' —  ', ' — ').rstrip(' —').strip()

    if len(rendered) > max_len:
        # Trim title only; keep the "— site_name" suffix intact when
        # possible.
        if ' — ' in rendered and site_name:
            head, _, _ = rendered.partition(' — ')
            allowed = max_len - len(site_name) - 3   # space-dash-space
            if allowed > 10:
                rendered = head[:allowed].rstrip() + ' — ' + site_name
            else:
                rendered = rendered[:max_len]
        else:
            rendered = rendered[:max_len]

    return rendered


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

    # Auto-noindex thin PDPs (PluginConfig['seo']['noindex_thin_pdp_below_words']).
    # When a product's description has fewer than N words AND we're
    # on a page that resolves to that product, bump robots to
    # noindex,follow so Google doesn't index the shell page until the
    # merchant fills in the copy. 0 disables — default disabled.
    try:
        if (
            object is not None
            and 'noindex' not in meta.robots
            and getattr(object, '_meta', None) is not None
            and getattr(object._meta, 'model_name', '') == 'product'
        ):
            from plugins.registry import plugin_registry
            seo_plugin = None
            for attr in ('get', 'get_plugin'):
                fn = getattr(plugin_registry, attr, None)
                if callable(fn):
                    try:
                        seo_plugin = fn('seo')
                    except Exception:  # noqa: BLE001
                        continue
                    if seo_plugin is not None:
                        break
            min_words = 0
            if seo_plugin is not None:
                try:
                    min_words = int(seo_plugin.get_config_value(
                        'noindex_thin_pdp_below_words', 0,
                    ) or 0)
                except (TypeError, ValueError):
                    min_words = 0
            if min_words > 0:
                desc = (getattr(object, 'description', '') or '').strip()
                # Cheap word count — split on whitespace, skip empties.
                word_count = len([w for w in desc.split() if w])
                if word_count < min_words:
                    meta.robots = 'noindex, follow'
    except Exception:  # noqa: BLE001 — never break PDP render over an SEO heuristic
        pass

    return mark_safe(meta.to_html())


@register.simple_tag
def seo_preconnect():
    """Emit <link rel="preconnect"> for the configured CDN host.

    Driven by PluginConfig['seo']['preconnect_to_cdn']. Empty config →
    no tag. Speeds first image load when product media is served from
    a separate CDN (Cloudflare Images, S3 + CloudFront, etc.).
    """
    host = ''
    try:
        from plugins.registry import plugin_registry
        seo_plugin = None
        for attr in ('get', 'get_plugin'):
            fn = getattr(plugin_registry, attr, None)
            if callable(fn):
                try:
                    seo_plugin = fn('seo')
                except Exception:  # noqa: BLE001
                    continue
                if seo_plugin is not None:
                    break
        if seo_plugin is not None:
            host = (seo_plugin.get_config_value('preconnect_to_cdn', '') or '').strip()
    except Exception:  # noqa: BLE001
        return ''
    if not host:
        return ''
    # Add the scheme if the merchant only wrote the bare host.
    if not host.startswith(('http://', 'https://')):
        host = 'https://' + host
    safe = escape(host)
    return mark_safe(
        f'<link rel="preconnect" href="{safe}" crossorigin>'
        f'<link rel="dns-prefetch" href="{safe}">'
    )


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
                         priority=False, css_class='', style='',
                         view_transition_name='', img_id=''):
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

    # Respect PluginConfig['seo']['lazy_load_below_fold_images']. When
    # the merchant disabled lazy loading, every <img> renders with
    # loading="eager" — usually a bad idea (hurts LCP, wastes
    # bandwidth) but some themes / CDN setups misbehave with the
    # native lazy-load attribute. Defaults to ON.
    lazy_enabled = True
    try:
        from plugins.registry import plugin_registry
        seo_plugin = None
        for attr in ('get', 'get_plugin'):
            fn = getattr(plugin_registry, attr, None)
            if callable(fn):
                try:
                    seo_plugin = fn('seo')
                except Exception:  # noqa: BLE001
                    continue
                if seo_plugin is not None:
                    break
        if seo_plugin is not None:
            lazy_enabled = bool(seo_plugin.get_config_value(
                'lazy_load_below_fold_images', True,
            ))
    except Exception:  # noqa: BLE001
        pass

    def _loading_for(is_priority: bool) -> str:
        if is_priority:
            return 'eager'
        return 'lazy' if lazy_enabled else 'eager'

    # Strip absolute prefix; we only resize images under MEDIA_ROOT.
    if url.startswith('http://') or url.startswith('https://'):
        # Best-effort: keep the original URL; skip resize for off-site.
        loading = _loading_for(priority)
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
    loading = _loading_for(priority)
    fp = ' fetchpriority="high"' if priority else ''
    sizes_attr = f' sizes="{escape(sizes)}"' if sizes else ''
    class_attr = f' class="{escape(css_class)}"' if css_class else ''
    # Compose style: caller-supplied first, then view-transition-name
    # appended so a PLP card can hand off cleanly into the PDP hero.
    final_style = ''
    if style:
        final_style = style if style.rstrip().endswith(';') else style.rstrip() + ';'
    if view_transition_name:
        final_style += f' view-transition-name: {view_transition_name};'
    style_attr = f' style="{escape(final_style.strip())}"' if final_style else ''
    id_attr = f' id="{escape(img_id)}"' if img_id else ''
    # data-src-rel lets JS (e.g. PDP gallery swap) rewrite the
    # <source srcset> + <img> src from a relative media path.
    data_attr = f' data-src-rel="{escape(rel)}"'

    return mark_safe(
        f'<picture>'
        f'<source type="image/avif" srcset="{escape(srcset_for("avif"))}"{sizes_attr}>'
        f'<source type="image/webp" srcset="{escape(srcset_for("webp"))}"{sizes_attr}>'
        f'<img src="{escape(fallback)}" alt="{escape(alt)}" '
        f'loading="{loading}" decoding="async"{fp}'
        f'{class_attr}{style_attr}{id_attr}{data_attr}>'
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


@register.simple_tag(takes_context=True)
def seo_search_results_jsonld(context, items, query=''):
    """Emit SearchResultsPage + ItemList for a /search/ page.
    `items` is a list of {name, url, image}.
    """
    if not items:
        return ''
    request = context.get('request')
    try:
        url = request.build_absolute_uri() if request else ''
    except Exception:  # noqa: BLE001
        url = ''
    from plugins.installed.seo.services import _jsonld_dump
    item_list = [
        {
            '@type': 'ListItem',
            'position': i + 1,
            'url': it.get('url') or '',
            'name': it.get('name') or '',
        }
        for i, it in enumerate(items)
    ]
    obj = {
        '@context': 'https://schema.org',
        '@type': 'SearchResultsPage',
        'url': url,
        'name': f'Search results for {query}' if query else 'Search results',
        'mainEntity': {
            '@type': 'ItemList',
            'numberOfItems': len(items),
            'itemListElement': item_list,
        },
    }
    return mark_safe(f'<script type="application/ld+json">{_jsonld_dump(obj)}</script>')


@register.simple_tag(takes_context=True)
def seo_person_jsonld(context, name, slug='', sameas=None):
    """Person JSON-LD for author landing pages. `sameas` is an
    optional iterable of URLs (LinkedIn / ORCID / Wikidata / etc.)
    that prove the entity's identity.
    """
    if not name:
        return ''
    request = context.get('request')
    try:
        url = request.build_absolute_uri() if request else ''
    except Exception:  # noqa: BLE001
        url = ''
    from plugins.installed.seo.services import _jsonld_dump
    obj = {
        '@context': 'https://schema.org',
        '@type': 'Person',
        'name': name,
        'url': url,
    }
    if sameas:
        obj['sameAs'] = [u for u in sameas if u]
    return mark_safe(f'<script type="application/ld+json">{_jsonld_dump(obj)}</script>')


@register.simple_tag(takes_context=True)
def seo_aboutpage_jsonld(context, name='', description=''):
    """AboutPage JSON-LD with mainEntity → Organization. Used on /about/."""
    from plugins.installed.seo.services import organization_jsonld, _jsonld_dump
    request = context.get('request')
    try:
        url = request.build_absolute_uri() if request else ''
    except Exception:  # noqa: BLE001
        url = ''
    org = organization_jsonld() or {}
    org.pop('@context', None)
    obj = {
        '@context': 'https://schema.org',
        '@type': 'AboutPage',
        'name': name or 'About',
        'url': url,
    }
    if description:
        obj['description'] = description
    if org:
        obj['mainEntity'] = org
    return mark_safe(f'<script type="application/ld+json">{_jsonld_dump(obj)}</script>')


@register.simple_tag(takes_context=True)
def seo_contactpage_jsonld(context, name='', description=''):
    """ContactPage JSON-LD with mainEntity → Organization + ContactPoint."""
    from core.models import StoreSettings
    from plugins.installed.seo.services import organization_jsonld, _jsonld_dump
    request = context.get('request')
    try:
        url = request.build_absolute_uri() if request else ''
    except Exception:  # noqa: BLE001
        url = ''
    org = organization_jsonld() or {}
    org.pop('@context', None)
    email = StoreSettings.get('contact_email', '') or ''
    phone = StoreSettings.get('support_phone', '') or ''
    if email or phone:
        cp = {'@type': 'ContactPoint', 'contactType': 'customer support'}
        if email:
            cp['email'] = email
        if phone:
            cp['telephone'] = phone
        org['contactPoint'] = cp
    obj = {
        '@context': 'https://schema.org',
        '@type': 'ContactPage',
        'name': name or 'Contact',
        'url': url,
    }
    if description:
        obj['description'] = description
    if org:
        obj['mainEntity'] = org
    return mark_safe(f'<script type="application/ld+json">{_jsonld_dump(obj)}</script>')


@register.simple_tag
def seo_llms_link():
    """Emit a <link rel="alternate"> hint to /llms.txt for LLM crawlers."""
    from plugins.installed.seo.services import site_settings
    s = site_settings()
    if not s.llms_txt_enabled:
        return ''
    return mark_safe('<link rel="alternate" type="text/plain" href="/llms.txt" title="LLM-friendly site map">')
