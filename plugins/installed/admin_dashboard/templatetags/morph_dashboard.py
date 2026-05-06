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
