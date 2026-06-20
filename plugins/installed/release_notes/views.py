"""Version & updates page — renders docs/RELEASE_NOTES.md.

Dependency-free: the release notes use a small, fixed subset of markdown (###/####
headings, - lists, **bold**, `code`, [links], paragraphs), so we render it with a
tiny built-in converter rather than pulling in a markdown library that isn't used
anywhere else in the platform. Everything is HTML-escaped first, so marking the
result safe is sound. `parse_releases` is pure + tested.
"""

from __future__ import annotations

import html as _html
import re
from pathlib import Path

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils.safestring import mark_safe

_HEADING = re.compile(r'^##\s+(.*)$', re.MULTILINE)
_VERSION = re.compile(r'(v[\w.\-]+)\s*[—\-–(]*\s*([\d]{4}-[\d]{2}-[\d]{2})?')
_LINK = re.compile(r'\[([^\]]+)\]\((https?://[^)\s]+)\)')
_BOLD = re.compile(r'\*\*([^*]+)\*\*')
_CODE = re.compile(r'`([^`]+)`')


def _release_notes_path() -> Path:
    return Path(settings.BASE_DIR) / 'docs' / 'RELEASE_NOTES.md'


def _inline(text: str) -> str:
    """Escape, then apply safe inline formatting (links / bold / code)."""
    t = _html.escape(text)
    t = _LINK.sub(r'<a href="\2" rel="noopener" target="_blank">\1</a>', t)
    t = _BOLD.sub(r'<strong>\1</strong>', t)
    t = _CODE.sub(r'<code>\1</code>', t)
    return t


def _md_to_html(body: str) -> str:
    """Minimal markdown → HTML for the release-notes subset. Input is escaped."""
    out: list[str] = []
    para: list[str] = []
    in_list = False

    def flush_para():
        if para:
            out.append('<p>' + ' '.join(para) + '</p>')
            para.clear()

    def close_list():
        nonlocal in_list
        if in_list:
            out.append('</ul>')
            in_list = False

    for raw in body.split('\n'):
        line = raw.strip()
        if not line:
            flush_para()
            close_list()
            continue
        h = re.match(r'^(#{3,4})\s+(.*)', line)
        if h:
            flush_para()
            close_list()
            level = len(h.group(1))
            out.append(f'<h{level}>{_inline(h.group(2))}</h{level}>')
            continue
        b = re.match(r'^[-*]\s+(.*)', line)
        if b:
            flush_para()
            if not in_list:
                out.append('<ul>')
                in_list = True
            out.append('<li>' + _inline(b.group(1)) + '</li>')
            continue
        close_list()
        para.append(_inline(line))
    flush_para()
    close_list()
    return '\n'.join(out)


def parse_releases(raw: str) -> list[dict]:
    """Split RELEASE_NOTES.md on `## ` headings into release cards.

    Returns ``[{version, date, title, html}]`` newest-first (document order).
    A `## ` section whose heading isn't a version still renders, keyed by its
    raw heading.
    """
    out: list[dict] = []
    matches = list(_HEADING.finditer(raw))
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        body = raw[m.end() : (matches[i + 1].start() if i + 1 < len(matches) else len(raw))]
        vm = _VERSION.match(heading)
        version = vm.group(1) if vm else ''
        date = vm.group(2) if (vm and vm.group(2)) else ''
        out.append(
            # All content is HTML-escaped inside _md_to_html → safe to mark.
            {
                'version': version,
                'date': date,
                'title': heading,
                'html': mark_safe(_md_to_html(body.strip())),  # noqa: S308
            }
        )
    return out


@staff_member_required
def version_updates(request):
    version = getattr(settings, 'MORPHEUS_VERSION', 'v0.1.0')
    path = _release_notes_path()
    releases: list[dict] = []
    if path.exists():
        try:
            releases = parse_releases(path.read_text(encoding='utf-8'))
        except Exception:  # noqa: BLE001 — never break the page on a doc glitch
            releases = []
    return render(
        request,
        'release_notes/index.html',
        {
            'version': version,
            'releases': releases,
            'latest': releases[0] if releases else None,
        },
    )
