"""Template filters for parsing YouTube + Vimeo URLs into embed IDs."""
from __future__ import annotations

import re

from django import template

register = template.Library()


_YOUTUBE_PATTERNS = [
    re.compile(r'youtube\.com/watch\?v=([A-Za-z0-9_-]{6,})'),
    re.compile(r'youtu\.be/([A-Za-z0-9_-]{6,})'),
    re.compile(r'youtube\.com/embed/([A-Za-z0-9_-]{6,})'),
    re.compile(r'youtube\.com/shorts/([A-Za-z0-9_-]{6,})'),
]


@register.filter(name='youtube_id')
def youtube_id(url: str) -> str:
    """Return the 11-char video id from a YouTube URL, or ''."""
    if not url:
        return ''
    for pat in _YOUTUBE_PATTERNS:
        m = pat.search(url)
        if m:
            return m.group(1)
    return ''


_VIMEO_RE = re.compile(r'vimeo\.com/(?:video/)?(\d+)')


@register.filter(name='vimeo_id')
def vimeo_id(url: str) -> str:
    """Return the numeric id from a Vimeo URL, or ''."""
    if not url:
        return ''
    m = _VIMEO_RE.search(url)
    return m.group(1) if m else ''
