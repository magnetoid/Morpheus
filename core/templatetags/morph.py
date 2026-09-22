"""Core Morpheus template tags.

Exposes one tag — `{% storefront_blocks "slot_name" %}` — which renders
every plugin contribution registered against that slot, in priority
order. Themes use this to give plugins a place to draw on the
storefront without any plugin needing to monkey-patch templates.

Usage:

    {% load morph %}
    <main>
      ...
      {% storefront_blocks "home_below_grid" %}
      ...
    </main>
"""

# ruff: noqa: PLC0415, S308, PLR0911, I001
# - PLC0415: inline imports avoid app-registry-not-ready issues during
#   settings import + keep the templatetag module lightweight.
# - S308: mark_safe is applied to trusted, internally-rendered storefront
#   block HTML + curated markdown — never raw user input.
# - PLR0911 / I001: convert_money's branches are deliberate fallbacks;
#   import grouping inside helpers is per-function localised.
from __future__ import annotations

import logging
import re
from html import escape, unescape

from django import template
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

logger = logging.getLogger('morpheus.templatetags')

register = template.Library()

_SENTENCE_END = re.compile(r'[.!?](\s|$)')


@register.filter
def first_sentence(text) -> str:
    """First sentence of `text` — up to the first . ! or ?, trimmed, capped at
    180 chars; the whole (capped) string when there's no sentence break. Used on
    every theme's product card for a one-line pitch under the title.

    Normalises to PLAIN TEXT first: unescape entities (twice — some stored copy
    arrived pre-escaped, and `{% firstof … as %}` escapes once more) then strip
    markup, so a description holding ``<ul><li>…&#8217;s…`` renders as clean
    prose instead of literal ``&#8217;`` / ``<li>`` on the card.

    Lives in core (not book_product's book_extras, where it began) because the
    shared storefront card in every theme uses it, and a store can disable the
    book vertical — a book-plugin filter in a shared template 500s once that
    plugin is off.
    """
    s = ('' if text is None else str(text)).strip()
    if not s:
        return ''
    s = strip_tags(unescape(unescape(s))).strip()
    if not s:
        return ''
    m = _SENTENCE_END.search(s)
    out = s[: m.start() + 1] if m else s
    return out.strip()[:180]


@register.simple_tag
def plugin_enabled(slug: str) -> bool:
    """True when the plugin `slug` is currently active.

    Thin wrapper over ``app_registry.is_active`` so templates can gate
    a surface on a plugin without the brittle ``{% if 'x' in active_plugins
    %}`` string check. Use as a boolean::

        {% plugin_enabled "affiliates" as has_affiliates %}
        {% if has_affiliates %} ... {% endif %}

    Fail-soft: returns False if the registry can't be imported.
    """
    if not slug:
        return False
    try:
        from plugins.registry import app_registry
    except ImportError:
        return False
    return app_registry.is_active(slug)


@register.simple_tag(takes_context=True)
def storefront_blocks(context, slot: str) -> str:
    """Render every storefront block contributed for `slot`."""
    if not slot:
        return ''
    try:
        from plugins.registry import app_registry
    except ImportError:
        return ''

    blocks = app_registry.storefront_blocks_for(slot)
    if not blocks:
        return ''

    rendered_parts: list[str] = []
    request = context.get('request')
    base_ctx = {k: v for k, v in context.flatten().items() if k != 'block'}

    for block in blocks:
        try:
            rendered_parts.append(
                render_to_string(block.template, {**base_ctx, 'block': block}, request=request)
            )
        except Exception as e:  # noqa: BLE001 — never break the page on a bad block
            logger.warning(
                'storefront_blocks: %s/%s render failed: %s',
                block.plugin,
                block.slot,
                e,
                exc_info=True,
            )
    return mark_safe(''.join(rendered_parts))


@register.simple_tag(takes_context=True)
def storefront_head(context, title: str = '', description: str = '') -> str:
    """Render the whole SEO head: title, metas, canonical, robots, OG, JSON-LD.

    A theme calls this ONCE inside `<head>` and is done::

        <head>
          <meta charset="utf-8">
          {% storefront_head %}
          ...theme css/js...
        </head>

    The optional arguments are the *fallbacks* a shell guarantees on its own —
    `{% storefront_head title=page_title description=page_blurb %}`. When the
    view or an entity supplies better values, the SEO app replaces them; when no
    subscriber answers (the seo app is disabled or absent), the fallbacks are
    what renders, so the page still has a title.

    Themes must not emit their own `<title>`/canonical/robots/OG alongside this
    tag — that is how a page ends up with two of each.
    """
    from django.utils.translation import get_language

    from core.head import build_head

    request = context.get('request')
    flat = context.flatten()
    fallback_title = title or flat.get('page_title') or flat.get('seo_title') or ''
    fallback_description = (
        description or flat.get('meta_description') or flat.get('seo_description') or ''
    )

    try:
        doc = build_head(
            path=request.get_full_path() if request is not None else '',
            language=get_language() or '',
            request=request,
            context=flat,
            title=str(fallback_title or ''),
            description=str(fallback_description or ''),
        )
    except Exception as e:  # noqa: BLE001 — a head failure must not 500 the page
        logger.error('storefront_head: build failed: %s', e, exc_info=True)
        safe_title = escape(str(fallback_title or ''))
        return mark_safe(f'<title>{safe_title}</title>' if safe_title else '')

    if request is not None:
        # Marker read by the legacy `{% seo_* %}` shims (so a half-migrated theme
        # doesn't emit both) and by the head-injection middleware (so it doesn't
        # inject a second copy into a template that already called the tag).
        request._morpheus_head_rendered = True
    return mark_safe(doc.render())


_CURRENCY_SYMBOLS = {
    'USD': '$',
    'EUR': '€',
    'GBP': '£',
    'JPY': '¥',
    'AUD': 'A$',
    'CAD': 'C$',
    'NZD': 'NZ$',
    'CHF': 'CHF ',
    'CNY': '¥',
    'INR': '₹',
    'BRL': 'R$',
    'MXN': 'MX$',
    'KRW': '₩',
    'TRY': '₺',
    'RUB': '₽',
    'ZAR': 'R',
    'SEK': 'kr ',
    'NOK': 'kr ',
    'DKK': 'kr ',
    'PLN': 'zł ',
    'RSD': 'RSD ',
}


@register.filter(name='money')
def money_filter(value, _arg=None):
    """Render a Money instance OR a GraphQL `{amount, currency}` dict.

    Locale-aware formatting (sprint #20): uses the request locale's
    thousands + decimal separators when available — `€19,95` in de-DE,
    `€19.95` in en-US — falling back to the previous comma-thousands /
    dot-decimal style if Babel isn't installed.

    Templates render storefront prices coming from the GraphQL layer as
    dicts; without this filter Django prints the dict literal
    (`{'amount': '17.00', 'currency': 'USD'}`).
    """
    if value in (None, ''):
        return ''
    if isinstance(value, dict):
        amount = value.get('amount') or '0'
        currency = (value.get('currency') or 'USD').upper()
    else:
        amount = getattr(value, 'amount', value)
        currency = str(getattr(value, 'currency', 'USD')).upper()
    try:
        from decimal import Decimal  # noqa: PLC0415

        amount = Decimal(str(amount))
    except Exception:  # noqa: BLE001
        return f'{_CURRENCY_SYMBOLS.get(currency, currency + " ")}{amount}'

    # Locale-aware formatting via Babel when available; gracefully
    # fall back to the previous en-US style otherwise.
    try:
        from babel.numbers import format_currency  # noqa: PLC0415
        from django.utils.translation import get_language  # noqa: PLC0415

        locale_code = (get_language() or 'en').replace('-', '_')
        return format_currency(amount, currency, locale=locale_code)
    except Exception:  # noqa: BLE001
        formatted = f'{amount:,.2f}'
        symbol = _CURRENCY_SYMBOLS.get(currency, f'{currency} ')
        return f'{symbol}{formatted}'


@register.filter(name='convert')
def convert_money(value, target_currency: str):
    """Convert a Money value to the target currency using the latest ExchangeRate.

    No-op (returns value as-is) when:
    - value isn't a Money object,
    - source and target currencies match,
    - no ExchangeRate row exists for the pair.
    """
    if not value or not target_currency:
        return value
    try:
        from djmoney.money import Money
        from core.models import ExchangeRate
    except ImportError:
        return value
    if not isinstance(value, Money):
        return value
    src = str(value.currency)
    tgt = (target_currency or '').upper()[:3]
    if src == tgt:
        return value
    try:
        rate = ExchangeRate.objects.filter(base_currency=src, quote_currency=tgt).first()
    except Exception:  # noqa: BLE001
        return value
    if rate is None:
        return value
    from decimal import Decimal

    converted = (Decimal(value.amount) * Decimal(rate.rate)).quantize(Decimal('0.01'))
    return Money(converted, tgt)


def markdown_to_html(value: str) -> str:
    """Minimal Markdown → HTML for the subset our LLM produces.

    Handles: `## H2`, `### H3`, paragraph blocks, `[text](url)` inline
    links, `**bold**` / `*italic*`. Escapes everything else; the
    template filter wraps the output in `mark_safe`. Pulled out of the
    filter so management commands can reuse the same converter.
    """
    if not value:
        return ''
    import re
    from django.utils.html import escape as _esc

    def _inline(text: str) -> str:
        """Inline transforms applied AFTER block-level HTML escaping."""
        # [text](url) → anchor. The url piece gets re-escaped so any odd
        # characters can't break out of the href attribute.
        text = re.sub(
            r'\[([^\]]+)\]\(([^)\s]+)\)',
            lambda m: f'<a href="{_esc(m.group(2))}">{m.group(1)}</a>',
            text,
        )
        text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', text)
        return text

    # Insert blank lines around every `## ` / `### ` line so headings
    # always start their own block, even when the LLM omitted blank
    # lines between hook + heading + body (common — our prompt doesn't
    # enforce them). Then the simple block-split below works.
    norm = re.sub(r'\n(#{2,3} )', r'\n\n\1', str(value))
    norm = re.sub(r'(#{2,3} [^\n]+)\n(?!#|\n)', r'\1\n\n', norm)

    out = []
    for block in re.split(r'\n\s*\n', norm.strip()):
        b = block.strip()
        if not b:
            continue
        if b.startswith('### '):
            out.append(f'<h3>{_inline(_esc(b[4:].strip()))}</h3>')
        elif b.startswith('## '):
            out.append(f'<h2>{_inline(_esc(b[3:].strip()))}</h2>')
        else:
            esc = _esc(b).replace('\n', '<br>')
            out.append(f'<p>{_inline(esc)}</p>')
    return '\n'.join(out)


@register.filter(name='md', is_safe=True)
def markdown_safe(value):
    """Template-filter wrapper around ``markdown_to_html``."""
    return mark_safe(markdown_to_html(value))


# EU AI Act Art. 50(1) — the mandatory "you're talking to an AI" disclosure.
# The default text is a legal FLOOR that lives in core (never a togglable
# plugin), so it can't vanish when a plugin is disabled. gdpr may replace the
# wording via the AI_SURFACE_DISCLOSURE filter; a disabled gdpr falls back here.
_AI_DISCLOSURE_DEFAULT = (
    "You're chatting with an AI assistant, not a person. It can make mistakes — "
    'check important details before you rely on them.'
)


@register.simple_tag
def ai_disclosure(surface: str = '') -> str:
    """Render the Art. 50 AI-disclosure label for a conversational AI surface.

    Drop ``{% ai_disclosure surface="ai_stylist" %}`` inside any customer-facing
    AI chat template. Emits an accessible, machine-readable note; the wording is
    the core legal-floor default unless a subscriber (gdpr) overrides it through
    the ``AI_SURFACE_DISCLOSURE`` filter. Fail-soft: on any error the default
    text still renders — the disclosure must never silently disappear.
    """
    from django.utils.html import format_html

    text = _AI_DISCLOSURE_DEFAULT
    try:
        from core.hooks import MorpheusEvents, hook_registry

        filtered = hook_registry.filter(
            MorpheusEvents.AI_SURFACE_DISCLOSURE,
            value=_AI_DISCLOSURE_DEFAULT,
            surface=surface or '',
        )
        if isinstance(filtered, str) and filtered.strip():
            text = filtered.strip()
    except Exception:  # noqa: BLE001 — never let the disclosure fail to render.
        logger.debug('ai_disclosure filter failed; using default', exc_info=True)

    return format_html(
        '<p class="ai-disclosure" role="note" data-ai-disclosure data-ai-surface="{}">{}</p>',
        surface or '',
        text,
    )


@register.simple_tag
def image_frame_style() -> str:
    """CSS custom properties for the store's image frame, for either shell.

    Emits `--img-ratio` and `--img-fit` on `:root`, so a frame is written

        aspect-ratio: var(--img-ratio); object-fit: var(--img-fit);

    and the merchant's choice restyles the dashboard, the media library and
    the storefront together. Before this, six dashboard frames and every
    theme card hardcoded `2 / 3` — a book cover — so a store selling anything
    else showed square photographs letterboxed into portrait slots with no
    setting that could change it.

    `original` resolves to `auto`, which in `aspect-ratio` means "impose no
    frame"; the image then keeps the proportions it was uploaded with.
    """
    from core.images import configured_display_settings

    try:
        settings_ = configured_display_settings()
    except Exception:  # noqa: BLE001 — a style tag must never 500 a page
        logger.warning('image_frame_style: could not read image settings', exc_info=True)
        return ''
    if settings_ is None:
        # No explicit choice: emit nothing and let each surface's own fallback
        # stand, so an existing storefront is not reshaped without being asked.
        return ''
    return mark_safe(
        '<style>:root{'
        f'--img-ratio:{escape(settings_["ratio"])};'
        f'--img-fit:{escape(settings_["fit"])};'
        '}</style>'
    )
