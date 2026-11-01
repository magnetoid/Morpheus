"""How a stored email reads in the dashboard inbox.

Mail is HTML from anyone on the internet. It is shown sanitised: no scripts,
styles, images or attributes beyond a link's address, so it cannot run code,
stretch the page, or load anything from the sender (a remote image tells the
sender the mail was opened). A plain-text mail keeps its line breaks. The quoted
earlier message folds under "Show quoted text".
"""

from __future__ import annotations

import re
from email.header import decode_header, make_header

import bleach
from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe

_TAGS = [
    'a', 'b', 'blockquote', 'br', 'caption', 'code', 'div', 'em', 'h1', 'h2', 'h3',
    'h4', 'h5', 'h6', 'hr', 'i', 'li', 'ol', 'p', 'pre', 's', 'small', 'span',
    'strong', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot', 'th', 'thead', 'tr',
    'u', 'ul',
]  # fmt: skip
_ATTRS = {'a': ['href', 'title'], 'td': ['colspan', 'rowspan'], 'th': ['colspan', 'rowspan']}
_PROTOCOLS = ['http', 'https', 'mailto']

# bleach keeps the text of a tag it strips, so the elements whose text is not the
# message (a stylesheet, a script, a hidden preheader) go first, comments included.
_COMMENTS = re.compile(r'<!--.*?-->', re.S)
_NOT_TEXT = re.compile(r'<(style|script|head|title|xml)\b[^>]*>.*?</\1\s*>', re.I | re.S)
_HIDDEN = re.compile(
    r'<(span|div|p|td)\b[^>]*style\s*=\s*["\'][^"\']*display\s*:\s*none[^>]*>.*?</\1\s*>',
    re.I | re.S,
)
_IMAGE = re.compile(r'<img\b', re.I)

# Where a mail client starts the earlier message it quotes.
_HTML_QUOTE = re.compile(
    r'<(?:div|blockquote)\b[^>]*(?:class\s*=\s*["\']?(?:gmail_quote|yahoo_quoted|moz-cite-prefix)'
    r'|type\s*=\s*["\']?cite|id\s*=\s*["\']?(?:divRplyFwdMsg|appendonsend))',
    re.I,
)
_TEXT_QUOTE = re.compile(
    r'^(?:On\b[^\n]*(?:\n[^\n]*)?\bwrote:[ \t]*$|-{2,}\s*Original Message\s*-{2,})',
    re.M | re.I,
)


def header_text(value) -> str:
    """A header as people read it: ``=?UTF-8?Q?Podr=C5=A1ka?=`` becomes ``Podrška``."""
    value = str(value or '')
    if '=?' not in value:
        return value
    try:
        return str(make_header(decode_header(value)))
    except (LookupError, UnicodeDecodeError, ValueError):
        return value


def _link_attrs(attrs, new=False):
    attrs[(None, 'rel')] = 'nofollow noopener noreferrer'
    attrs[(None, 'target')] = '_blank'
    return attrs


def _linked(markup: str) -> str:
    return bleach.linkify(markup, callbacks=[_link_attrs])


def _clean_html(html: str) -> str:
    html = _HIDDEN.sub('', _NOT_TEXT.sub('', _COMMENTS.sub('', html)))
    cleaned = bleach.clean(html, tags=_TAGS, attributes=_ATTRS, protocols=_PROTOCOLS, strip=True)
    return _linked(cleaned)


def _split_html(html: str) -> tuple[str, str]:
    m = _HTML_QUOTE.search(html)
    if m is None or not bleach.clean(html[: m.start()], tags=[], strip=True).strip():
        return html, ''
    return html[: m.start()], html[m.start() :]


def _split_text(text: str) -> tuple[str, str]:
    starts = [m.start() for m in _TEXT_QUOTE.finditer(text)]
    lines = text.split('\n')
    first_quoted = None
    for n in range(len(lines) - 1, -1, -1):
        if lines[n].startswith('>'):
            first_quoted = n
        elif lines[n].strip():
            break
    if first_quoted is not None:
        starts.append(sum(len(line) + 1 for line in lines[:first_quoted]))
    starts = [s for s in starts if text[:s].strip()]
    if not starts:
        return text, ''
    at = min(starts)
    return text[:at].rstrip(), text[at:]


def render_body(message) -> SafeString:
    """The message's body as safe markup for the inbox (HTML first, like a mail client)."""
    html = message.body_html or ''
    if html.strip():
        kind, images = 'html', len(_IMAGE.findall(html))
        main, quoted = (_clean_html(part) for part in _split_html(html))
    else:
        text = (message.body_text or '').replace('\r\n', '\n').replace('\r', '\n').strip('\n')
        kind, images = 'text', 0
        main, quoted = (_linked(escape(part)) for part in _split_text(text))
    parts = [f'<div class="crm-mail-body crm-mail-{kind}">{main}']
    if quoted.strip():
        parts.append(
            f'<details class="crm-mail-quote"><summary>Show quoted text</summary>{quoted}</details>'
        )
    parts.append('</div>')
    if images:
        parts.append('<p class="crm-mail-note">Images in this email are not shown.</p>')
    return mark_safe(''.join(parts))  # noqa: S308 — every part above went through bleach or escape
