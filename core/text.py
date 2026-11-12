"""Plain text out of what a merchant or a model wrote, and cut to fit.

Shared by every app that publishes a short form of a longer text (a meta
description, a story caption, an article body in structured data): a raw slice
ends in the middle of a word, or inside a tag or an entity.
"""

from __future__ import annotations

import html
import re

_SENTENCE_END = re.compile(r'[.!?…](?=\s|$)')

# Markdown a model writes into an article: images, links, bold and italic,
# headings, list bullets and quotes. Rendered to the text a reader sees.
_MD_IMAGE = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
_MD_LINK = re.compile(r'\[([^\]]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
_MD_STRONG = re.compile(r'(\*\*|__)(?=\S)(.+?)(?<=\S)\1')
_MD_EM = re.compile(r'(?<![*\w])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![*\w])')
_MD_LINE_MARK = re.compile(r'(?m)^[ \t]*(?:#{1,6}[ \t]+|>[ \t]?|[-*+][ \t]+(?=\S))')
_MD_IMAGE_SRC = re.compile(r'!\[[^\]]*\]\(([^)\s]+)')
_HTML_IMAGE_SRC = re.compile(r"""<img\b[^>]*?\ssrc=["']([^"']+)["']""", re.I)

_SKIPPED = re.compile(r'(?is)<(script|style|template|noscript)\b.*?</\1\s*>')
_BREAK_TAG = re.compile(
    r'(?i)</?(?:p|div|br|li|ul|ol|h[1-6]|blockquote|section|article|tr|td|th|table|figure|figcaption)\b[^>]*>'
)
_TAG = re.compile(r'<[^>]*>')
_SPACE = re.compile(r'\s+')


def clip(text: str, limit: int) -> str:
    """``text`` cut to ``limit`` characters at a sentence end, else a word (…)."""
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    window = text[:limit]
    floor = int(limit * 0.5)
    sentence_end = -1
    for m in _SENTENCE_END.finditer(window):
        if m.end() >= floor:
            sentence_end = m.end()
    if sentence_end > 0:
        return window[:sentence_end].strip()
    cut = window[: limit - 1]
    space = cut.rfind(' ')
    if space >= floor:
        cut = cut[:space]
    return cut.rstrip(' ,;:–-') + '…'


def render_markdown_text(value: str) -> str:
    """Markdown's markers turned into the text a reader sees: ``**word**`` → word,
    ``[text](url)`` → text, an image → nothing, a heading's ``##`` → gone.

    HTML in the value is left as it is, so it suits a body that mixes both.
    """
    text = str(value or '')
    text = _MD_IMAGE.sub(' ', text)
    text = _MD_LINK.sub(r'\1', text)
    text = _MD_STRONG.sub(r'\2', text)
    text = _MD_EM.sub(r'\1', text)
    return _MD_LINE_MARK.sub('', text)


def plain_text(value) -> str:
    """One line of plain text from rich HTML or markdown: markdown rendered first,
    then tags stripped (a block ends a word), entities unescaped, spaces collapsed."""
    text = render_markdown_text(str(value or ''))
    text = _SKIPPED.sub(' ', text)
    text = _BREAK_TAG.sub(' ', text)
    text = _TAG.sub('', text)
    return _SPACE.sub(' ', html.unescape(text)).strip()


def first_markdown_image(value) -> str:
    """The address of the first ``![alt](src)`` image in a text, or ''."""
    m = _MD_IMAGE_SRC.search(str(value or ''))
    return m.group(1).strip() if m else ''


def body_images(value) -> list[str]:
    """The addresses of a text's images in the order they appear: ``<img src>``
    and markdown ``![alt](src)`` alike."""
    text = str(value or '')
    found = [(m.start(), m.group(1).strip()) for m in _HTML_IMAGE_SRC.finditer(text)]
    found += [(m.start(), m.group(1).strip()) for m in _MD_IMAGE_SRC.finditer(text)]
    urls: list[str] = []
    for _at, url in sorted(found):
        if url and url not in urls:
            urls.append(url)
    return urls
