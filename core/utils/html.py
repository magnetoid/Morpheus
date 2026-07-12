"""Shared HTML sanitiser for staff/AI-authored rich text rendered with ``|safe``.

Any model field whose value reaches a template through ``|safe`` (product
descriptions, CMS bodies, section rich-text) MUST be sanitised on save — a
compromised staff session, a GraphQL/agent write, or prompt-injected LLM output
would otherwise persist stored XSS. This is the single allowlist; ``cms`` keeps
its own richer allowlist (iframes/tables) for long-form editorial pages.
"""

from __future__ import annotations

import bleach

# Deliberately narrower than the CMS allowlist: product copy is short rich text,
# not embeds. No iframe/script/style; links are http/https/mailto only.
_ALLOWED_TAGS = [
    'p',
    'br',
    'strong',
    'b',
    'em',
    'i',
    'u',
    's',
    'a',
    'ul',
    'ol',
    'li',
    'blockquote',
    'code',
    'pre',
    'h2',
    'h3',
    'h4',
    'span',
    'hr',
]
_ALLOWED_ATTRS = {
    '*': ['class'],
    'a': ['href', 'title', 'target', 'rel'],
}
_ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


def sanitize_richtext(html: str) -> str:
    """Strip non-allowlisted tags/attrs/protocols from rich text.

    Returns the input unchanged when falsy (empty/None) so callers can assign
    the result back unconditionally.
    """
    if not html:
        return html
    return bleach.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )
