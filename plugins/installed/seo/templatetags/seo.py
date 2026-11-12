"""
Template tags for the SEO plugin that a page's BODY may use.

    {% load seo %}
    {% seo_responsive_image product.image alt=product.name sizes="(min-width: 900px) 40vw, 100vw" %}

The `<head>` is not here. Title, description, canonical, robots, hreflang,
Open Graph and the one JSON-LD graph are assembled by the `STOREFRONT_HEAD`
filter and rendered once by core's `{% storefront_head %}` (core/head.py, ADR
0036). The per-tag head helpers (`{% seo_meta %}`, `{% seo_*_jsonld %}`,
`{% seo_*_og %}`, `{% seo_hreflang %}`, …) were deprecated in v0.46.0 and
removed in v0.164.0; `themes/test_head_contract.py` fails a template that
still calls one.
"""

# ruff: noqa: PLC0415, S308, S110, S112, PLR0912, PLR0915, PLW2901
# mark_safe is load-bearing: every helper returns trusted HTML built from
# escape()-d values. The inline imports keep optional apps soft.

from __future__ import annotations

from django import template
from django.utils.html import conditional_escape, escape
from django.utils.safestring import mark_safe

register = template.Library()


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

    if not title:
        # A page that passes no title (e.g. the homepage) reads as the brand —
        # never "Untitled — <brand>". Render the site name alone.
        return (site_name or 'Untitled')[:max_len]

    try:
        rendered = template_str.format(
            title=title,
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
            allowed = max_len - len(site_name) - 3  # space-dash-space
            if allowed > 10:
                rendered = head[:allowed].rstrip() + ' — ' + site_name
            else:
                rendered = rendered[:max_len]
        else:
            rendered = rendered[:max_len]

    return rendered


@register.simple_tag(takes_context=True)
def seo_ai_answer_block(context, product) -> dict:
    """Data for the PDP "Key facts" / AI-answer storefront block.

    Returns ``{enabled, answer, facts}``:
      * ``answer`` — the quotable TL;DR (seo.ai_answer metafield),
      * ``facts``  — up to ~6 ``(label, value)`` pairs pulled from the
        ``book`` metafield namespace (author, format, pages, ISBN, …),
      * ``enabled`` — the merchant's ``ai_answer_block_enabled`` toggle.

    Rendering a concise, machine-quotable summary on the PDP itself is
    the highest-leverage AEO move: AI engines lift the on-page answer,
    not just the JSON-LD. Empty/disabled → the template renders nothing.
    """
    out = {'enabled': False, 'answer': '', 'facts': []}
    if product is None:
        return out
    try:
        from plugins.installed.seo.services import site_settings  # noqa: PLC0415

        out['enabled'] = bool(getattr(site_settings(), 'ai_answer_block_enabled', False))
    except Exception:  # noqa: BLE001
        out['enabled'] = False
    if not out['enabled']:
        return out

    try:
        from plugins.installed.seo.services._helpers import ai_answer_for  # noqa: PLC0415

        out['answer'] = ai_answer_for(product)
    except Exception:  # noqa: BLE001
        out['answer'] = ''

    # Key facts from the `book` metafield namespace — labelled + ordered
    # so the block reads like a spec table an AI can parse cleanly.
    try:
        from plugins.installed.book_product.compat import book_attrs  # noqa: PLC0415

        meta = book_attrs(product)  # model-first, legacy book.* fallback
        label_order = [
            ('author', 'Author'),
            ('publisher', 'Publisher'),
            ('format', 'Format'),
            ('pages', 'Pages'),
            ('published_year', 'Published'),
            ('language', 'Language'),
            ('isbn', 'ISBN'),
        ]
        facts = []
        for key, label in label_order:
            val = meta.get(key)
            if val not in (None, '', []):
                facts.append((label, str(val)))
        out['facts'] = facts[:6]
    except Exception:  # noqa: BLE001
        out['facts'] = []
    return out


@register.inclusion_tag('seo/_meta_panel.html', takes_context=True)
def seo_meta_panel(context, obj):
    """Render the reusable per-object SEO settings panel for ``obj``.

    Drop ``{% seo_meta_panel page %}`` into any dashboard edit form; persist on
    save with ``seo.services.panel.save_object_seo(obj, request.POST)``. The
    panel posts ``seo_*`` fields backed by the ``SeoMeta`` override + the
    ``seo.ai_answer`` metafield — one editor for every content type.
    """
    from plugins.installed.seo.services.panel import panel_context

    return panel_context(obj, context.get('request'))


@register.simple_tag
def seo_responsive_image(
    src,
    alt='',
    sizes='',
    widths='400,800,1200',
    priority=False,
    css_class='',
    style='',
    view_transition_name='',
    img_id='',
):
    """Emit a <picture> element with AVIF + WebP sources + a JPEG/PNG
    fallback `<img>`, generated via /img/<fmt>/<w>/... on demand.

    Args:
      src: absolute media URL (e.g. ``/media/products/foo.jpg``) or a
        Django FieldFile-like object with a ``.url`` attribute.
      alt: required alt text. Falls back to '' (mark decorative). Text a template
        already escaped (a ``blocktrans asvar``) is not escaped twice.
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
        from plugins.registry import app_registry

        seo_plugin = None
        for attr in ('get', 'get_plugin'):
            fn = getattr(app_registry, attr, None)
            if callable(fn):
                try:
                    seo_plugin = fn('seo')
                except Exception:  # noqa: BLE001
                    continue
                if seo_plugin is not None:
                    break
        if seo_plugin is not None:
            lazy_enabled = bool(
                seo_plugin.get_config_value(
                    'lazy_load_below_fold_images',
                    True,
                )
            )
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
            f'<img src="{escape(url)}" alt="{conditional_escape(alt)}" '
            f'loading="{loading}" decoding="async"{fp} '
            f'{f"class={css_class!r}" if css_class else ""} '
            f'{f"style={style!r}" if style else ""}>'
        )
    media_prefix = '/media/'
    if not url.startswith(media_prefix):
        return mark_safe(f'<img src="{escape(url)}" alt="{conditional_escape(alt)}">')
    rel = url[len(media_prefix) :]

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
    # Every attribute value here is an absolute URL on purpose. A bare storage
    # path (`data-src-rel="products/x.jpg"`, which nothing read) was resolved
    # against the page by crawlers and logged ~13k 404s a month on one store.

    # The fallback's own size, so the browser keeps the image's box before it
    # loads (the /img/ variant only ever scales down). `data-sized` meets seo's
    # zero-specificity `width:auto; height:auto` in the head: a theme that sizes
    # the image keeps its rules, and one that does not keeps today's layout.
    size_attr = ''
    from plugins.installed.seo.services.images import image_size

    natural = image_size(url)
    if natural:
        nat_w, nat_h = natural
        box_w = min(fallback_w, nat_w)
        box_h = max(1, round(nat_h * box_w / nat_w))
        size_attr = f' width="{box_w}" height="{box_h}" data-sized'

    return mark_safe(
        f'<picture>'
        f'<source type="image/avif" srcset="{escape(srcset_for("avif"))}"{sizes_attr}>'
        f'<source type="image/webp" srcset="{escape(srcset_for("webp"))}"{sizes_attr}>'
        f'<img src="{escape(fallback)}" alt="{conditional_escape(alt)}"{size_attr} '
        f'loading="{loading}" decoding="async"{fp}'
        f'{class_attr}{style_attr}{id_attr}>'
        f'</picture>'
    )
