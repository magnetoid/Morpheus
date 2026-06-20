"""Version & updates page — renders docs/RELEASE_NOTES.md.

The markdown is a repo-controlled doc (not user input), so rendering it to HTML
and marking it safe is fine. `parse_releases` is pure + tested.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils.safestring import mark_safe

_HEADING = re.compile(r'^##\s+(.*)$', re.MULTILINE)
_VERSION = re.compile(r'(v[\w.\-]+)\s*[—\-–(]*\s*([\d]{4}-[\d]{2}-[\d]{2})?')


def _release_notes_path() -> Path:
    return Path(settings.BASE_DIR) / 'docs' / 'RELEASE_NOTES.md'


def parse_releases(raw: str) -> list[dict]:
    """Split RELEASE_NOTES.md on `## ` headings into release cards.

    Returns ``[{version, date, title, html}]`` newest-first (document order).
    A `## ` section whose heading isn't a version still renders, keyed by its
    raw heading.
    """
    import markdown  # noqa: PLC0415

    out: list[dict] = []
    matches = list(_HEADING.finditer(raw))
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        body = raw[m.end() : (matches[i + 1].start() if i + 1 < len(matches) else len(raw))]
        vm = _VERSION.match(heading)
        version = vm.group(1) if vm else ''
        date = vm.group(2) if (vm and vm.group(2)) else ''
        html = markdown.markdown(body.strip(), extensions=['extra', 'sane_lists', 'nl2br'])
        out.append(
            # Repo-controlled doc (not user input) → safe to render as HTML.
            {'version': version, 'date': date, 'title': heading, 'html': mark_safe(html)}  # noqa: S308
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
