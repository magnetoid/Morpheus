"""A guide's Markdown as safe HTML for the Help page, and as text.

The subset guides use: ``##``/``###`` headings, paragraphs, ``-`` and ``1.`` lists,
``**bold**``, `` `code` ``, ``https://`` links and markers (help_markers.py).
Every character is escaped before a tag is added, so marking the HTML safe is
sound. ``plain`` is the guide for Linda (markers become names and paths) and
``readable`` the words search matches.
"""

from __future__ import annotations

import html
import re

from django.utils.safestring import SafeString, mark_safe

from plugins import app_help
from plugins.installed.release_notes import help_markers

_URL_LINK = re.compile(r'\[([^\]]+)\]\((https://[^)\s]+)\)')
_BOLD = re.compile(r'\*\*([^*]+)\*\*')
_CODE = re.compile(r'`([^`]+)`')
_HEAD = re.compile(r'^(#{2,3})\s+(.*)$')
_BULLET = re.compile(r'^[-*]\s+(.*)$')
_NUMBER = re.compile(r'^\d+[.)]\s+(.*)$')


def _marker_html(m, app: str) -> str:
    text, kind, target = m.group(1), m.group(2), m.group(3)  # text is escaped already
    link = help_markers.resolve(kind, target, app=app)
    if link is None:
        return text
    shown = text or html.escape(link.label)
    if link.url:
        return f'<a href="{html.escape(link.url)}">{shown}</a>'
    if link.off:
        return f'{shown} <span class="help-off">(when the app is on)</span>'
    return shown


def _inline(text: str, app: str) -> str:
    t = html.escape(text)
    t = app_help.MARKER_RE.sub(lambda m: _marker_html(m, app), t)
    t = _URL_LINK.sub(r'<a href="\2" rel="noopener" target="_blank">\1</a>', t)
    t = _BOLD.sub(r'<strong>\1</strong>', t)
    return _CODE.sub(r'<code>\1</code>', t)


def render(body: str, *, app: str) -> SafeString:
    """The guide's body as HTML."""
    out: list[str] = []
    para: list[str] = []
    open_list = ''

    def flush() -> None:
        if para:
            out.append('<p>' + ' '.join(para) + '</p>')
            para.clear()

    def close() -> None:
        nonlocal open_list
        if open_list:
            out.append(f'</{open_list}>')
            open_list = ''

    for raw in body.split('\n'):
        line = raw.strip()
        if not line:
            flush()
            close()
            continue
        head = _HEAD.match(line)
        if head:
            flush()
            close()
            level = len(head.group(1))
            out.append(f'<h{level}>{_inline(head.group(2), app)}</h{level}>')
            continue
        item, tag = _BULLET.match(line), 'ul'
        if item is None:
            item, tag = _NUMBER.match(line), 'ol'
        if item is not None:
            flush()
            if open_list != tag:
                close()
                out.append(f'<{tag}>')
                open_list = tag
            out.append(f'<li>{_inline(item.group(1), app)}</li>')
            continue
        close()
        para.append(_inline(line, app))
    flush()
    close()
    return mark_safe('\n'.join(out))  # noqa: S308 — every character escaped in _inline


def plain(body: str, *, app: str) -> str:
    """The guide as text for Linda: markers become their names and paths."""

    def marker(m) -> str:
        link = help_markers.resolve(m.group(2), m.group(3), app=app)
        if link is None:
            return m.group(1)
        name = m.group(1) or link.label
        if link.url:
            return f'{name} ({link.url})'
        return f'{name} (when the app is on)' if link.off else name

    text = app_help.MARKER_RE.sub(marker, body)
    text = _URL_LINK.sub(r'\1 (\2)', text)
    return _BOLD.sub(r'\1', text).replace('`', '')


def readable(body: str, *, app: str) -> str:
    """The guide as words only, for search: no paths, no Markdown marks."""

    def marker(m) -> str:
        if m.group(1):
            return m.group(1)
        link = help_markers.resolve(m.group(2), m.group(3), app=app)
        return link.label if link is not None else ''

    text = app_help.MARKER_RE.sub(marker, body)
    text = _URL_LINK.sub(r'\1', text)
    text = re.sub(r'(?m)^#{1,6}\s+', '', text)
    return _BOLD.sub(r'\1', text).replace('`', '')
