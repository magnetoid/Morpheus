"""Dashboard cards — the widgets apps put on a section's landing page.

An app contributes ``DashboardCard(section=…)``; the shell adds a few of its
own (``CORE_CARDS``). ``cards_for(section, request)`` returns them ready to
draw, in order, each normalised to one shape so every card looks the same
whoever wrote it. The landing pages render them with
``{% dashboard_card_list "<section>" as cards %}`` +
``admin_dashboard/_cards.html``.

A card's data callable is app code running inside a shell page, so it is
fenced: an exception becomes the card's error state (and an ERROR log line
with the traceback), never a broken page — and never a card that silently
isn't there, which is what a bare ``except: pass`` would make of it.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger('morpheus.admin')

_TONES = ('ok', 'warn', 'danger')
MAX_ROWS = 5


@dataclass(frozen=True)
class CoreCard:
    """A card the shell itself draws, from a shell function."""

    section: str
    title: str
    data: str  # dotted path to `(request) -> dict | None`
    url: str = ''
    cta: str = 'Open'
    icon: str = 'circle'
    order: int = 100
    capability: str = ''
    plugin: str = ''


CORE_CARDS: tuple[CoreCard, ...] = (
    CoreCard(
        'products',
        'Content audit',
        'plugins.installed.admin_dashboard.views_split.products.content_audit_card',
        url='/dashboard/products/content-audit/',
        cta='Open audit',
        icon='clipboard-check',
        order=90,
        capability='catalog.read',
    ),
)


def _resolve(data: Any):
    if callable(data):
        return data
    module_name, _, attr = str(data).rpartition('.')
    return getattr(importlib.import_module(module_name), attr)


def _allowed(card, user) -> bool:
    if not card.capability:
        return True
    from core.authz import enforcement_mode, has_capability  # noqa: PLC0415

    # The same rule as a page's @require_capability: only `enforce` denies.
    return enforcement_mode() != 'enforce' or has_capability(user, card.capability)


def _rows(raw) -> list[dict]:
    rows = []
    for row in list(raw or [])[:MAX_ROWS]:
        if isinstance(row, dict):
            rows.append(
                {
                    'label': str(row.get('label', '')),
                    'value': row.get('value', ''),
                    'url': row.get('url', ''),
                }
            )
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            rows.append(
                {'label': str(row[0]), 'value': row[1], 'url': row[2] if len(row) > 2 else ''}
            )
    return rows


def _draw(card, request) -> dict | None:
    """One card, ready for `_cards.html`, or None when it has nothing to say."""
    base = {
        'key': f'{card.plugin or "core"}:{card.title}',
        'title': card.title,
        'icon': card.icon or 'circle',
        'url': card.url,
        'cta': card.cta or 'Open',
        'value': '',
        'caption': '',
        'rows': [],
        'tone': '',
        'empty': '',
        'error': False,
    }
    try:
        data = _resolve(card.data)(request)
    except Exception:
        logger.exception('dashboard card %r (%s) failed', card.title, card.plugin or 'core')
        return {**base, 'error': True}
    if data is None:
        return None
    if not isinstance(data, dict):
        logger.error('dashboard card %r returned %r, not a dict', card.title, type(data))
        return {**base, 'error': True}
    value = data.get('value', '')
    return {
        **base,
        'url': data.get('url') or card.url,
        'value': '' if value is None else str(value),
        'caption': str(data.get('caption') or ''),
        'rows': _rows(data.get('rows')),
        'tone': data.get('tone') if data.get('tone') in _TONES else '',
        'empty': str(data.get('empty') or ''),
    }


def cards_for(section: str, request) -> list[dict]:
    """Every card for a section's landing — the shell's and every active
    app's — in order, drawn. Apps' legacy section keys are resolved."""
    from plugins.installed.admin_dashboard import navigation  # noqa: PLC0415
    from plugins.registry import app_registry  # noqa: PLC0415

    user = getattr(request, 'user', None)
    contributed = [
        c
        for c in app_registry.dashboard_cards()
        if navigation.main_section_key(c.section) == section
    ]
    own = [c for c in CORE_CARDS if c.section == section]
    out = []
    for card in sorted(own + contributed, key=lambda c: (c.order, c.title)):
        if not _allowed(card, user):
            continue
        drawn = _draw(card, request)
        if drawn is not None:
            out.append(drawn)
    return out
