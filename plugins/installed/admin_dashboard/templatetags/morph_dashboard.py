"""Dashboard-specific template helpers.

Two inclusion tags:
- ``{% sparkline series stroke=… %}`` — tiny SVG line chart for KPI tiles.
- ``{% filter_chips request param=label … %}`` — renders an "Active
  filters" row of removable pills based on the current ``request.GET``.
  Each chip's × link drops just that one param while keeping the rest.
"""
from __future__ import annotations

from django import template
from django.http import QueryDict
from django.utils.safestring import mark_safe

register = template.Library()


@register.inclusion_tag('admin_dashboard/_sparkline.html')
def sparkline(series, width: int = 120, height: int = 28, stroke: str = ''):
    """Render an inline-SVG sparkline.

    `series` — list of numbers, oldest → newest.
    `stroke` — optional colour. The home view passes the metric's
    `trend` ('up' | 'down' | 'flat'); we map that to a CSS variable.
    """
    nums = [float(x or 0) for x in (series or [])]
    if len(nums) < 2:
        return {'series': nums, 'series_points': '', 'series_max': 0}
    mx = max(nums)
    if mx <= 0:
        return {'series': nums, 'series_points': '', 'series_max': 0}
    n = len(nums)
    step = width / (n - 1)
    pts = []
    for i, v in enumerate(nums):
        x = round(i * step, 2)
        # SVG y-axis grows downward; invert + 2px padding so the line
        # never grazes the top/bottom edge.
        y = round(height - 2 - (v / mx) * (height - 4), 2)
        pts.append(f'{x},{y}')
    stroke_color = {
        'up':   'var(--success)',
        'down': 'var(--danger)',
        'flat': 'var(--text-muted)',
    }.get(stroke, stroke or 'var(--text-muted)')
    return {
        'series': nums,
        'series_points': ' '.join(pts),
        'series_max': mx,
        'width': width,
        'height': height,
        'stroke': stroke_color,
    }


@register.simple_tag(takes_context=True)
def sort_link(context, field, label):
    """Render a sortable column header.

    Usage in a `<th>`::

        <th>{% sort_link "total" "Total" %}</th>

    The link's URL flips ``?dir=`` if `field` already matches the current
    sort, otherwise sets ``?sort=field&dir=asc``. Always drops `page=`
    so changing sort returns to page 1. The chevron next to the label
    reflects the current direction (▲ asc, ▼ desc, faded ⇅ when
    inactive).
    """
    request = context.get('request')
    cur_sort = context.get('sort') or ''
    cur_dir = context.get('dir') or 'asc'

    base = QueryDict(mutable=True)
    if request is not None:
        for k, v in request.GET.lists():
            for vv in v:
                base.appendlist(k, vv)
    base.pop('page', None)
    base['sort'] = field
    if cur_sort == field:
        base['dir'] = 'asc' if cur_dir == 'desc' else 'desc'
    else:
        base['dir'] = 'asc'
    href = (request.path if request else '') + '?' + base.urlencode()

    if cur_sort == field:
        chevron = '▲' if cur_dir == 'asc' else '▼'
        chev_color = 'var(--text)'
    else:
        chevron = '⇅'
        chev_color = 'var(--text-subtle)'

    return mark_safe(
        f'<a href="{href}" class="inline-flex items-center gap-1" '
        f'style="color: inherit;">'
        f'{label}<span style="font-size:.75em; color:{chev_color};">{chevron}</span>'
        f'</a>'
    )


@register.inclusion_tag('admin_dashboard/_tabs.html', takes_context=True)
def index_tabs(context, param, choices, counts=None):
    """Render an underlined tab strip for an index page status filter.

    Usage::

        {% index_tabs param="status" choices=status_choices counts=status_counts %}

    `param` is the GET key the tabs control (e.g. "status").
    `choices` is an iterable of `(value, label)` pairs. The first entry is
    typically `("", "All")` — the empty value means "no filter".
    `counts` is an optional `{value: int}` dict used to render a small
    pill next to each label. Pass `None` to omit counts.

    Each tab's href clones `request.GET`, replaces `param`, and **drops
    `page=`** — so flipping tabs returns to page 1 instead of stranding
    the user on page 17 of a now-shorter list.
    """
    request = context.get('request')
    tabs = []
    current = (request.GET.get(param, '') if request else '') or ''
    base_get = QueryDict(mutable=True)
    if request is not None:
        for k, v in request.GET.lists():
            for vv in v:
                base_get.appendlist(k, vv)
    for value, label in choices:
        params = base_get.copy()
        params.pop('page', None)
        if value:
            params[param] = value
        else:
            params.pop(param, None)
        qs = params.urlencode()
        href = (request.path if request else '') + (('?' + qs) if qs else '')
        count = None
        if counts is not None and value:
            count = counts.get(value, 0)
        elif counts is not None and not value:
            count = sum(counts.values()) if counts else 0
        tabs.append({
            'label': label,
            'value': value,
            'count': count,
            'active': current == value,
            'href': href,
        })
    return {'tabs': tabs}


@register.inclusion_tag('admin_dashboard/_filter_chips.html', takes_context=True)
def filter_chips(context, **labels):
    """Render chips for any request.GET param that has a non-empty value.

    Usage::

        {% filter_chips q="Search" status="Status" source="Source" %}

    Each kwarg maps a query-string key → display label. Display value
    comes from ``request.GET[key]`` verbatim. The "remove" link
    rebuilds the URL without that one param, preserving the rest.
    """
    request = context.get('request')
    if request is None:
        return {'chips': []}
    chips = []
    for key, label in labels.items():
        raw = (request.GET.get(key) or '').strip()
        if not raw:
            continue
        # Build remove URL: same path + GET minus this key.
        rest = QueryDict(mutable=True)
        for k, v in request.GET.items():
            if k != key and v:
                rest[k] = v
        qs = rest.urlencode()
        remove_url = request.path + (('?' + qs) if qs else '')
        chips.append({
            'label': label,
            'value': raw,
            'remove_url': remove_url,
        })
    return {'chips': chips}
