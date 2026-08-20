"""SeoTemplate resolution — bulk title/description patterns, applied at render.

A merchant writes ONE pattern per page kind ("{name} — buy online | {site_name}")
instead of typing a meta title on every product. Templates are a *resolution
layer*, not a bulk write: nothing is stamped onto rows, so editing the pattern
re-titles every page it covers on the next render, and deleting it falls back
to exactly what resolution produced before. Precedence stays honest to the P1
lesson (a value a human typed beats one the platform generated):

    merchant SeoMeta / native column          ← always wins in `empty_only` mode
      → matching SeoTemplate                  ← fills the gaps (or, in `all`
      → the page's own default (fallbacks)       mode, deliberately overrides)

Grammar (kept deliberately small):
    {name}                     field / metafield / contributed token
    {author|"Anonymous"}       alternatives, first non-empty wins; quoted = literal
    {name|truncate:40|title}   filters: truncate:N, title, lower, upper
    [ by {author}]             bracket block dropped whole if no token inside
                               resolved (so separators don't dangle)

Token vocabulary = the object's fields + bare metafield keys (services/tokens.py)
+ {site_name}/{sep} + whatever owners contribute via SEO_TEMPLATE_TOKENS
(book_product could add {author}; fired here, per-render).

Compiled per (kind, field) and cached; invalidated on SeoTemplate save/delete
(seo/signals.py) — the same shape as the IndexRule engine next door.
"""

from __future__ import annotations

import logging
import re

from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_KEY = 'seo:templates:v1'
_CACHE_TTL = 600

_TOKEN_RE = re.compile(r'\{([^{}]+)\}')
_BRACKET_RE = re.compile(r'\[([^\[\]]*)\]')
_FILTER_RE = re.compile(r'^(truncate:\d+|title|lower|upper)$')


# ── Compiled ruleset ─────────────────────────────────────────────────────────


def _compile() -> dict:
    """{(kind, field): [row dicts, most-specific first]} from active rows."""
    from plugins.installed.seo.models import SeoTemplate

    compiled: dict = {}
    rows = SeoTemplate.objects.filter(is_active=True).order_by('priority', 'created_at')
    for row in rows:
        compiled.setdefault((row.kind, row.field), []).append(
            {
                'template': row.template,
                'scope': row.scope,  # '' = global; else a category slug
                'mode': row.mode,
            }
        )
    # Scoped rows outrank global ones at equal priority.
    for key, entries in compiled.items():
        compiled[key] = sorted(entries, key=lambda e: (e['scope'] == '',))
    return compiled


def _rules() -> dict:
    got = cache.get(_CACHE_KEY)
    if got is None:
        got = _compile()
        cache.set(_CACHE_KEY, got, _CACHE_TTL)
    return got


def invalidate_templates() -> None:
    cache.delete(_CACHE_KEY)


# ── Object access (ORM instance or the PDP's GraphQL dict) ───────────────────


def _category_slug(obj) -> str:
    if obj is None:
        return ''
    if isinstance(obj, dict):
        cat = obj.get('category') or {}
        return str(cat.get('slug') or '') if isinstance(cat, dict) else ''
    cat = getattr(obj, 'category', None)
    return str(getattr(cat, 'slug', '') or '')


def _dict_field(obj: dict, key: str) -> str:
    """The PDP renders a GraphQL dict (camelCase); map the token vocabulary
    onto it so templates work on the page that matters most."""
    if key == 'name':
        return str(obj.get('name') or '')
    if key == 'sku':
        return str(obj.get('sku') or '')
    if key == 'category':
        cat = obj.get('category') or {}
        return str(cat.get('name') or '') if isinstance(cat, dict) else ''
    if key == 'price':
        price = obj.get('price') or {}
        if isinstance(price, dict) and price.get('amount') is not None:
            return f'{price.get("amount")} {price.get("currency") or ""}'.strip()
        return ''
    return str(obj.get(key) or '') if isinstance(obj.get(key), (str, int, float)) else ''


def _token_values(obj, kind: str) -> dict:
    """The full vocabulary for one render: site tokens + object fields +
    bare metafield keys + owner-contributed tokens."""
    from plugins.installed.seo.services.meta import site_settings

    site = site_settings()
    values: dict[str, str] = {
        'site_name': str(getattr(site, 'org_name', '') or ''),
        'sep': '—',
    }
    if isinstance(obj, dict):
        for key in ('name', 'sku', 'category', 'price'):
            values[key] = _dict_field(obj, key)
    elif obj is not None:
        from plugins.installed.seo.services.tokens import _FIELD_TOKENS, _metafields

        for key, _label in _FIELD_TOKENS:
            raw = getattr(obj, key, '')
            if key == 'category':
                raw = getattr(getattr(obj, 'category', None), 'name', '')
            values[key] = str(raw or '')
        for mk, mv in (_metafields(obj) or {}).items():
            values.setdefault(mk.split('.')[-1], str(mv or ''))
    try:
        from morpheus.core import MorpheusEvents, hook_registry

        extra = hook_registry.filter(MorpheusEvents.SEO_TEMPLATE_TOKENS, {}, obj=obj, kind=kind)
        for k, v in (extra or {}).items():
            values[str(k)] = str(v or '')
    except Exception:  # noqa: BLE001, S110 — contributed tokens must never break a render
        logger.debug('seo: SEO_TEMPLATE_TOKENS contribution failed', exc_info=True)
    return values


# ── The grammar ──────────────────────────────────────────────────────────────


def _apply_filter(value: str, spec: str) -> str:
    if spec.startswith('truncate:'):
        limit = int(spec.split(':', 1)[1])
        return value if len(value) <= limit else value[: max(0, limit - 1)].rstrip() + '…'
    if spec == 'title':
        return value.title()
    if spec == 'lower':
        return value.lower()
    if spec == 'upper':
        return value.upper()
    return value


def _eval_token(body: str, values: dict) -> tuple[str, bool]:
    """One `{…}` expression → (text, any_token_resolved).

    Segments split on `|`: a quoted segment is a literal, a filter-shaped
    segment is a filter, anything else is a token name tried in order until
    one resolves non-empty. Filters apply to whatever the chain produced.
    """
    resolved = ''
    matched = False
    filters: list[str] = []
    for segment in (s.strip() for s in body.split('|')):
        if not segment:
            continue
        if _FILTER_RE.match(segment):
            filters.append(segment)
            continue
        if len(segment) >= 2 and segment[0] == '"' and segment[-1] == '"':
            if not resolved:
                resolved = segment[1:-1]
            continue
        if not resolved:
            value = values.get(segment, '')
            if value:
                resolved = value
                matched = True
    for spec in filters:
        resolved = _apply_filter(resolved, spec)
    return resolved, matched


def render_template(text: str, obj, kind: str = '') -> str:
    """Render one pattern against one object. Empty result = template declined
    (a pattern whose every token is empty produces '', so the caller falls back
    rather than publishing bare separators)."""
    if not text:
        return ''
    values = _token_values(obj, kind)
    any_matched = False

    def _bracket(match: re.Match) -> str:
        inner = match.group(1)
        inner_matched = False

        def _tok(m: re.Match) -> str:
            nonlocal inner_matched
            out, ok = _eval_token(m.group(1), values)
            inner_matched = inner_matched or ok
            return out

        rendered = _TOKEN_RE.sub(_tok, inner)
        return rendered if inner_matched else ''

    text = _BRACKET_RE.sub(_bracket, text)

    def _tok(m: re.Match) -> str:
        nonlocal any_matched
        out, ok = _eval_token(m.group(1), values)
        any_matched = any_matched or ok
        return out

    out = re.sub(r'\s+', ' ', _TOKEN_RE.sub(_tok, text)).strip()
    # A render in which not a single token resolved is boilerplate, not a
    # title — decline so resolution falls through to the page's own default.
    return out if any_matched else ''


# ── Resolution hook (called from resolve_meta) ───────────────────────────────


def apply_templates(kind: str, obj, title: str, description: str) -> tuple[str, str]:
    """Apply the matching template per field. `title`/`description` arrive as
    the merchant's stored values ('' when none); `empty_only` fills gaps,
    `all` deliberately overrides. Fail-soft: any error returns the inputs."""
    try:
        rules = _rules()
        out = {'title': title, 'description': description}
        slug = _category_slug(obj)
        for field in ('title', 'description'):
            for entry in rules.get((kind, field), []):
                if entry['scope'] and entry['scope'] != slug:
                    continue
                if entry['mode'] == 'empty_only' and out[field]:
                    break  # a human value stands; scoped/global alike
                rendered = render_template(entry['template'], obj, kind)
                if rendered:
                    out[field] = rendered
                break  # first matching rule decides; priority ordered them
        return out['title'], out['description']
    except Exception:  # noqa: BLE001 — templating must never break meta resolution
        return title, description
