"""Strict allow-list sanitizer for ProductVideo.embed_html.

Pure stdlib (no bleach dep). We accept exactly one shape: a single
`<iframe>` whose `src` resolves to a known video host. Everything else
becomes empty string — defense in depth against XSS from a compromised
or malicious admin account.

The PDP block template ([`pdp_videos.html`](../templates/product_videos/blocks/pdp_videos.html))
falls back to the auto-embed path (`url` field) when `embed_html` is
empty, so rejecting a paste degrades gracefully.
"""

from __future__ import annotations

import re
from html import escape
from urllib.parse import urlparse

# Hosts we accept iframe `src=` from. Subdomain match is anchored to the
# end so `evilyoutube.com` doesn't slip through.
_ALLOWED_HOSTS: tuple[str, ...] = (
    'youtube.com',
    'youtu.be',
    'youtube-nocookie.com',
    'vimeo.com',
    'player.vimeo.com',
)

# Attributes we'll keep on the iframe. Anything else (incl. on* event
# handlers) is dropped. width/height come through as numerics only.
_ALLOWED_ATTRS: frozenset[str] = frozenset(
    {
        'src',
        'width',
        'height',
        'frameborder',
        'allow',
        'allowfullscreen',
        'loading',
        'referrerpolicy',
        'title',
    }
)

# Numeric-only attributes (drop the attribute if value isn't all digits).
_NUMERIC_ATTRS: frozenset[str] = frozenset({'width', 'height', 'frameborder'})

# Crude but tight extractor — we don't try to parse arbitrary HTML, only
# pull the FIRST <iframe ...> tag. Anything outside it is discarded.
_IFRAME_RE = re.compile(r'<\s*iframe\b([^>]*?)(?:/\s*>|>\s*</\s*iframe\s*>|>)', re.I | re.S)
_ATTR_RE = re.compile(r"""([a-zA-Z\-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""")


def _host_allowed(src: str) -> bool:
    try:
        host = (urlparse(src).hostname or '').lower()
    except Exception:  # noqa: BLE001
        return False
    if not host:
        return False
    return any(host == h or host.endswith('.' + h) for h in _ALLOWED_HOSTS)


def _scheme_safe(src: str) -> bool:
    """Reject javascript:, data:, vbscript:, file:, …"""
    return bool(re.match(r'^https?://', src or '', re.I))


def sanitize_embed_html(raw: str) -> str:
    """Return a sanitized `<iframe>` from `raw`, or empty string if no
    safe iframe is present. Idempotent."""
    if not raw or not raw.strip():
        return ''

    m = _IFRAME_RE.search(raw)
    if not m:
        return ''

    attrs_str = m.group(1) or ''
    out_attrs: dict[str, str] = {}

    for am in _ATTR_RE.finditer(attrs_str):
        name = am.group(1).lower()
        if name not in _ALLOWED_ATTRS:
            continue
        # boolean attribute (allowfullscreen) — keep without value
        value = am.group(2) or am.group(3) or am.group(4) or ''
        if name == 'src':
            if not (_scheme_safe(value) and _host_allowed(value)):
                return ''  # bad src → reject the whole iframe
        elif name in _NUMERIC_ATTRS:  # noqa: SIM102
            if not re.fullmatch(r'\d+', value):
                continue
        # Strip newlines / quotes that would let an attacker break out
        # of the attribute context after the escape below.
        value = re.sub(r'[\r\n]', ' ', value).strip()
        out_attrs[name] = value

    if 'src' not in out_attrs:
        return ''

    # Rebuild — every value goes through `escape(..., quote=True)` so
    # closing `"` inside a value can't escape the attribute.
    parts = []
    for name, value in out_attrs.items():
        if name == 'allowfullscreen' and value == '':
            parts.append('allowfullscreen')
        else:
            parts.append(f'{name}="{escape(value, quote=True)}"')
    return f'<iframe {" ".join(parts)}></iframe>'
