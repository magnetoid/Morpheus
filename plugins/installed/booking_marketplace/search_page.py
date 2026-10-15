"""What a search on the travel store asks for, and how its page says so.

The list views and the search bar read the request through `read_params`, so the bar
always shows what the results were filtered by: a known region, a date from today on,
a live category named by its slug or its name. The page's heading, its filter chips and
its empty-state line are built here (docs/superpowers/specs/2026-10-14-montenegro-search-design.md).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext as _

# Django's own `sr` catalog names days and months in Cyrillic (суб., Окт.) on a store
# written in Latin. Babel and the browser's Intl both follow CLDR, so the server's label
# and search.js's agree.
_DATE_LOCALES = {'sr': ('sr_Latn_ME', 'sr-Latn-ME')}
_DEFAULT_DATE_LOCALE = ('en_GB', 'en-GB')
QUERY_MAX_CHARS = 200


@dataclass(frozen=True)
class SearchParams:
    """A search, validated: anything unknown or unusable is dropped, never echoed."""

    q: str = ''
    region: str = ''
    region_label: str = ''
    day: datetime.date | None = None
    date_note: str = ''
    category: object = None  # a catalog Category


def read_params(request) -> SearchParams:
    """The search in `request.GET`."""
    from plugins.installed.booking_marketplace.models import REGIONS

    get = request.GET
    labels = {key: str(label) for key, label in REGIONS}
    region = (get.get('region') or '').strip()
    if region not in labels:
        region = ''
    day, note = _day(get.get('date'))
    return SearchParams(
        q=(get.get('q') or '').strip()[:QUERY_MAX_CHARS],
        region=region,
        region_label=labels.get(region, ''),
        day=day,
        date_note=note,
        category=_category(get.get('category')),
    )


def _day(raw) -> tuple[datetime.date | None, str]:
    raw = (raw or '').strip()
    if not raw:
        return None, ''
    try:
        day = datetime.date.fromisoformat(raw)
    except ValueError:
        return None, ''
    if day < timezone.localdate():
        return None, _('Choose a date from today on')
    return day, ''


def _category(raw):
    """An active category named by its slug or its exact name, in any case."""
    from django.db.models import Q

    from plugins.installed.catalog.models import Category

    raw = (raw or '').strip()
    if not raw:
        return None
    return Category.objects.filter(
        Q(slug__iexact=raw) | Q(name__iexact=raw), is_active=True
    ).first()


def date_locale() -> tuple[str, str]:
    """(Babel, browser) locale for dates in the visitor's language."""
    return _DATE_LOCALES.get((get_language() or 'en').split('-')[0], _DEFAULT_DATE_LOCALE)


def date_label(day) -> str:
    """'Sun 18 Oct' or 'ned 18. okt'; '' without a date."""
    if day is None:
        return ''
    try:
        from babel.dates import format_skeleton

        return format_skeleton('MMMEd', day, locale=date_locale()[0])
    except Exception:  # noqa: BLE001 — Babel arrives with py-moneyed; a label never fails a page
        return day.isoformat()


def values(params: SearchParams) -> dict:
    """What the search bar shows of a search."""
    category = params.category
    return {
        'q': params.q,
        'region': params.region,
        'region_label': params.region_label,
        'date_iso': params.day.isoformat() if params.day else '',
        'date_label': date_label(params.day),
        'date_note': params.date_note,
        'category': category.slug if category is not None else '',
        'category_label': category.name if category is not None else '',
    }


def heading(params: SearchParams) -> str:
    """The results page's h1: the query, else the category, else the plain title; then the date."""
    title = _title(params)
    if params.day:
        return _('%(title)s on %(date)s') % {'title': title, 'date': date_label(params.day)}
    return title


def _title(params: SearchParams) -> str:
    if params.q:
        if params.region_label:
            return _('“%(q)s” in %(region)s') % {'q': params.q, 'region': params.region_label}
        return _('“%(q)s” in Montenegro') % {'q': params.q}
    if params.category is not None:
        name = params.category.name
        if params.region_label:
            return _('%(category)s experiences in %(region)s') % {
                'category': name,
                'region': params.region_label,
            }
        return _('%(category)s experiences in Montenegro') % {'category': name}
    return _('Experiences in Montenegro')


def chips(request, params: SearchParams) -> list[dict]:
    """One removable chip per filter in force; its link is this page without it."""
    shown = []
    if params.q:
        shown.append(('q', _('“%(q)s”') % {'q': params.q}))
    if params.region:
        shown.append(('region', params.region_label))
    if params.day:
        shown.append(('date', date_label(params.day)))
    if params.category is not None:
        shown.append(('category', params.category.name))
    return [{'param': p, 'label': label, 'href': _without(request, p)} for p, label in shown]


def _without(request, param: str) -> str:
    query = request.GET.copy()
    for key in (param, 'page'):
        query.pop(key, None)
    encoded = query.urlencode()
    return f'{request.path}?{encoded}' if encoded else request.path


def empty_message(params: SearchParams, *, kind: str = 'experience') -> str:
    """What the page says when nothing matches every word, or nothing at all."""
    if kind == 'product':
        if params.q:
            return _('No products match “%(q)s”') % {'q': params.q}
        return _('No products match your search.')
    when = date_label(params.day)
    if params.q and when:
        return _('No experiences match “%(q)s” on %(date)s') % {'q': params.q, 'date': when}
    if params.q:
        return _('No experiences match “%(q)s”') % {'q': params.q}
    if when:
        return _('Nothing left to book on %(date)s') % {'date': when}
    return _('No experiences match your search.')


def page_context(request, params: SearchParams, *, close=False, kind='experience') -> dict:
    """The `search` a results page renders (list.html) and its search bar reads."""
    return {
        **values(params),
        'heading': heading(params),
        'chips': chips(request, params),
        'clear_url': request.path,
        'close': close,
        'card_heading': 'h3' if close else 'h2',
        'empty_message': empty_message(params, kind=kind),
    }
