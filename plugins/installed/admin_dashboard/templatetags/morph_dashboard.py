"""Dashboard-specific template helpers.

Right now: a single inclusion tag, ``{% sparkline series stroke="…" %}``,
that renders a tiny SVG line chart from a list of numbers. Used on
the home dashboard's KPI tiles. Skipped silently when the series is
empty / all zeros.
"""
from __future__ import annotations

from django import template

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
