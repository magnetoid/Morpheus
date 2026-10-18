"""Search across every installed app's help (the Help index's search box).

A small in-memory index of each app's label, summary, headings and guide words,
built once per process and version (guides change only with a deploy; under
DEBUG it is rebuilt every time). Case and accents fold, every word must match
somewhere, and a hit in the label ranks above the summary, a heading, then the
guide's text. Plain substring matching: a query is never a pattern.
"""

from __future__ import annotations

import unicodedata

from django.conf import settings

from plugins import app_help
from plugins.installed.release_notes import help_render

_WEIGHTS = (('label', 8), ('summary', 4), ('headings', 2), ('body', 1))
SNIPPET = 160
_cache: dict[str, list[dict]] = {}


def fold(text: str) -> str:
    decomposed = unicodedata.normalize('NFKD', text or '')
    return ''.join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def forget() -> None:
    _cache.clear()


def _index() -> list[dict]:
    from plugins.registry import app_registry

    key = str(getattr(settings, 'MORPHEUS_VERSION', ''))
    if not settings.DEBUG and key in _cache:
        return _cache[key]
    rows = []
    for inst in app_registry.all_plugins():
        guide = app_help.guide(inst.name)
        rows.append(
            {
                'name': inst.name,
                'label': inst.label or inst.name,
                'summary': (guide.summary if guide else '') or inst.description,
                'headings': ' '.join(guide.headings) if guide else '',
                'body': help_render.readable(guide.body, app=inst.name) if guide else '',
            }
        )
    _cache.clear()
    _cache[key] = rows
    return rows


def _snippet(body: str, terms: list[str]) -> str:
    folded = fold(body)
    found = [i for i in (folded.find(t) for t in terms) if i >= 0]
    if not found:
        return ''
    start = max(0, min(found) - SNIPPET // 3)
    piece = ' '.join(body[start : start + SNIPPET].split())
    return ('…' if start else '') + piece + ('…' if start + SNIPPET < len(body) else '')


def search(query: str, *, limit: int = 30) -> list[dict]:
    """Apps whose help mentions every word of ``query``, best first."""
    from plugins.registry import app_registry

    terms = fold(query).split()
    if not terms:
        return []
    hits = []
    for row in _index():
        fields = {name: fold(row[name]) for name, _weight in _WEIGHTS}
        score = 0
        for term in terms:
            best = max((w for name, w in _WEIGHTS if term in fields[name]), default=0)
            if not best:
                break
            score += best
        else:
            hits.append((score, row))
    hits.sort(key=lambda h: (-h[0], h[1]['label'].casefold()))
    return [
        {
            'name': row['name'],
            'label': row['label'],
            'summary': row['summary'],
            'snippet': _snippet(row['body'], terms),
            'active': app_registry.is_active(row['name']),
        }
        for _score, row in hits[:limit]
    ]
