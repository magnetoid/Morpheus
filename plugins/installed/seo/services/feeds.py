"""RSS 2.0 + Atom 1.0 feeds for the journal.

Mirrors the news-sitemap pattern in ``sitemaps.py``: read ``cms.Page``
rows tagged ``metadata.category == 'journal'`` (state=published),
ordered ``-publish_at``, sliced to the top 50.

Guards the ``Page`` import at module-load time so an uninstalled CMS
plugin returns a well-formed empty document instead of a 500.
"""

from __future__ import annotations

import contextlib
import re
from email.utils import format_datetime
from html import unescape
from urllib.parse import urljoin

from django.utils.html import escape

from ._helpers import _site_base_url, logger, site_settings

try:  # cms plugin is optional — degrade to empty feed when missing
    from plugins.installed.cms.models import Page as _Page
except Exception as _exc:  # noqa: BLE001 — cms plugin not installed
    logger.debug('seo.feeds: cms.Page unavailable at import time: %s', _exc)
    _Page = None  # type: ignore[assignment]

_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'\s+')


def _summary(body: str, max_chars: int = 280) -> str:
    """First ``max_chars`` of the body, HTML/Markdown stripped to plain text."""
    if not body:
        return ''
    text = _TAG_RE.sub(' ', str(body))
    text = unescape(text)
    text = _WS_RE.sub(' ', text).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + '…'
    return text


def _journal_posts(limit: int = 50):
    """Yield journal Page rows. Empty list when cms is uninstalled."""
    if _Page is None:
        return []
    try:
        return list(
            _Page.objects.filter(state='published', metadata__category='journal').order_by(
                '-publish_at'
            )[:limit]
        )
    except Exception as exc:  # noqa: BLE001 — DB not migrated yet
        logger.debug('seo.feeds: journal query failed: %s', exc)
        return []


def _author_of(post) -> str:
    md = getattr(post, 'metadata', None) or {}
    if not isinstance(md, dict):
        return ''
    val = md.get('author', '') or ''
    return str(val)


def render_journal_rss() -> str:
    """RSS 2.0 feed for the journal — top 50 published posts."""
    s = site_settings()
    base = _site_base_url().rstrip('/')
    channel_title = (s.organization_name or 'Journal').strip() + ' — Journal'
    channel_link = f'{base}/journal/'
    channel_desc = 'Latest journal posts.'

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">',
        '<channel>',
        f'<title>{escape(channel_title)}</title>',
        f'<link>{escape(channel_link)}</link>',
        f'<description>{escape(channel_desc)}</description>',
        '<language>en</language>',
        f'<atom:link href="{escape(urljoin(base + "/", "journal/feed.xml"))}" '
        'rel="self" type="application/rss+xml" />',
    ]

    for post in _journal_posts():
        url = f'{base}/journal/{post.slug}/'
        pub_at = post.publish_at or post.updated_at or post.created_at
        author = _author_of(post)
        summary = _summary(post.body)
        parts.append('<item>')
        parts.append(f'<title>{escape(post.title)}</title>')
        parts.append(f'<link>{escape(url)}</link>')
        parts.append(f'<guid isPermaLink="true">{escape(url)}</guid>')
        if pub_at is not None:
            with contextlib.suppress(Exception):
                parts.append(f'<pubDate>{escape(format_datetime(pub_at))}</pubDate>')
        if author:
            # dc:creator is friendlier than RSS's <author> (which wants
            # an email address). Namespace is declared on <rss>.
            parts.append(f'<dc:creator>{escape(author)}</dc:creator>')
        if summary:
            parts.append(f'<description>{escape(summary)}</description>')
        parts.append('</item>')

    parts.append('</channel>')
    parts.append('</rss>')
    return ''.join(parts)


def render_journal_atom() -> str:
    """Atom 1.0 feed for the journal — top 50 published posts."""
    s = site_settings()
    base = _site_base_url().rstrip('/')
    feed_title = (s.organization_name or 'Journal').strip() + ' — Journal'
    feed_self = urljoin(base + '/', 'journal/atom.xml')
    feed_alt = f'{base}/journal/'

    posts = _journal_posts()
    updated_iso = ''
    if posts:
        latest = posts[0].publish_at or posts[0].updated_at or posts[0].created_at
        if latest is not None:
            with contextlib.suppress(Exception):
                updated_iso = latest.replace(microsecond=0).isoformat()

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        f'<title>{escape(feed_title)}</title>',
        f'<link rel="self" type="application/atom+xml" href="{escape(feed_self)}"/>',
        f'<link rel="alternate" type="text/html" href="{escape(feed_alt)}"/>',
        f'<id>{escape(feed_self)}</id>',
    ]
    if updated_iso:
        parts.append(f'<updated>{escape(updated_iso)}</updated>')

    for post in posts:
        url = f'{base}/journal/{post.slug}/'
        pub_at = post.publish_at or post.updated_at or post.created_at
        author = _author_of(post)
        summary = _summary(post.body)
        parts.append('<entry>')
        parts.append(f'<title>{escape(post.title)}</title>')
        parts.append(f'<link rel="alternate" type="text/html" href="{escape(url)}"/>')
        parts.append(f'<id>{escape(url)}</id>')
        if pub_at is not None:
            with contextlib.suppress(Exception):
                iso = pub_at.replace(microsecond=0).isoformat()
                parts.append(f'<updated>{escape(iso)}</updated>')
                parts.append(f'<published>{escape(iso)}</published>')
        if author:
            parts.append(f'<author><name>{escape(author)}</name></author>')
        if summary:
            parts.append(f'<summary>{escape(summary)}</summary>')
        parts.append('</entry>')

    parts.append('</feed>')
    return ''.join(parts)
