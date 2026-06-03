"""Field/metafield token expansion for SEO title + description templates.

A merchant can write ``meta_title`` / ``meta_description`` with ``{tokens}`` —
native product fields (``{name}``, ``{sku}``, ``{category}``, ``{price}``) and
metafields (``{author}``, ``{isbn13}``, ``{publisher}``, …). ``resolve_meta``
expands them at render time; the product editor offers an "Insert field"
dropdown built from ``available_tokens()``. Unknown tokens are left literal so
typos are visible rather than silently dropped.
"""

# ruff: noqa: PLC0415
# Inline imports avoid circular deps with the metafields plugin + keep this
# importable before the app registry is ready.

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r'\{([a-z0-9_.]+)\}', re.IGNORECASE)

# Native product fields exposed as tokens (key, human label).
_FIELD_TOKENS: tuple[tuple[str, str], ...] = (
    ('name', 'Product name'),
    ('sku', 'SKU'),
    ('category', 'Category'),
    ('price', 'Price'),
)


def _field_value(obj, key: str) -> str:
    if obj is None:
        return ''
    if key == 'category':
        cat = getattr(obj, 'category', None)
        return str(getattr(cat, 'name', '') or '') if cat else ''
    if key == 'price':
        p = getattr(obj, 'display_price', None) or getattr(obj, 'price', None)
        return str(p) if p else ''
    return str(getattr(obj, key, '') or '')


def _metafields(obj) -> dict:
    """``{"namespace.key": value}`` for obj, or {} (fail-soft)."""
    try:
        from plugins.installed.metafields.models import Metafield

        return Metafield.objects.for_obj(obj) or {}
    except Exception:  # noqa: BLE001
        return {}


def expand_tokens(text: str, obj) -> str:
    """Replace ``{token}`` in ``text`` with product field / metafield values.

    Tokens resolve against native fields first, then metafields by full
    ``namespace.key`` and by bare ``key``. Unknown tokens are left untouched.
    No-op for empty text, dict products, or text without a ``{``.
    """
    if not text or '{' not in text or obj is None or isinstance(obj, dict):
        return text or ''
    mf = _metafields(obj)
    bare = {k.split('.')[-1]: v for k, v in mf.items()}
    field_keys = {fk for fk, _ in _FIELD_TOKENS}

    def repl(match: re.Match) -> str:
        key = match.group(1)
        if key in field_keys:
            return _field_value(obj, key)
        if key in mf:
            return str(mf[key])
        if key in bare:
            return str(bare[key])
        return match.group(0)  # leave unknown token literal

    return _TOKEN_RE.sub(repl, text)


def available_tokens(obj) -> list[dict]:
    """``[{token, label}]`` for the editor's "Insert field" dropdown."""
    out = [{'token': f'{{{k}}}', 'label': label} for k, label in _FIELD_TOKENS]
    seen = {t['token'] for t in out}
    for full_key in sorted(_metafields(obj)):
        bare = full_key.split('.')[-1]
        token = f'{{{bare}}}'
        if token in seen:
            continue
        seen.add(token)
        out.append({'token': token, 'label': f'{bare.replace("_", " ").title()} (metafield)'})
    return out
