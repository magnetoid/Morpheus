"""Fail-soft usage tracking + install-health math.

Two serve-time surfaces, both contributions (zero core edits):

  * **dashboard** — a context processor increments a per-day cache counter
    keyed by the *owning plugin* resolved from the ``/dashboard/…`` path.
  * **agent_tool** — a ``AgentEvents.TOOL_CALLING`` filter subscriber counts
    by the tool-name prefix (when it maps to an active plugin).

Counters live in the cache (Redis in prod, LocMem in dev/tests). An hourly
beat (``tasks.flush_usage_counters``) drains them into ``FeatureUsageDay``.
Everything here is wrapped so a failure never breaks a render or a tool call.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('morpheus.feature_adoption')

SURFACES = ('dashboard', 'agent_tool')
_KEY_TTL = 60 * 60 * 26  # 26h — outlive the hourly flush even across a gap

# Health-score weights (sum to 100).
BREADTH_PTS = 40
AGENT_PTS = 30
FRESH_PTS = 30
AGENT_CAP = 100  # tool calls / 30d that saturate the agent component
FRESH_WINDOW = 14  # days after which freshness decays to 0


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------


def _counter_key(day: date, plugin: str, surface: str) -> str:
    return f'feat_adopt:c:{day.isoformat()}:{plugin}:{surface}'


def _dirty_key(day: date) -> str:
    return f'feat_adopt:dirty:{day.isoformat()}'


def _incr(plugin: str, surface: str) -> None:
    """Bump today's counter for (plugin, surface) and note it as dirty."""
    if not plugin:
        return
    day = timezone.now().date()
    key = _counter_key(day, plugin, surface)
    try:
        cache.incr(key)
    except ValueError:
        cache.add(key, 1, _KEY_TTL)
    # Record which (plugin, surface) pairs the flush must drain — the cache
    # backend can't enumerate keys, so we keep our own dirty set.
    dkey = _dirty_key(day)
    dirty = cache.get(dkey) or set()
    tag = f'{plugin}|{surface}'
    if tag not in dirty:
        dirty.add(tag)
        cache.set(dkey, dirty, _KEY_TTL)


# ---------------------------------------------------------------------------
# Dashboard surface — context processor
# ---------------------------------------------------------------------------


def _second_segment(path: str) -> str:
    parts = [p for p in path.split('/') if p]
    if len(parts) >= 2 and parts[0] == 'dashboard':
        return parts[1]
    return ''


def _segment_plugin_map() -> dict[str, str]:
    """Map the first path segment of custom dashboard mounts to their plugin.

    Built from every contributed ``DashboardPage`` that overrides ``url``
    (e.g. ``/dashboard/subscriptions/`` → ``subscriptions``). Pages mounted at
    the default ``/dashboard/apps/<plugin>/…`` are handled directly in
    :func:`resolve_plugin`.
    """
    from plugins.registry import plugin_registry

    out: dict[str, str] = {}
    for page in plugin_registry.dashboard_pages():
        seg = _second_segment(getattr(page, 'url', '') or '')
        if seg and page.plugin:
            out.setdefault(seg, page.plugin)
    return out


def resolve_plugin(path: str) -> str | None:
    """Owning plugin for a ``/dashboard/…`` path, or ``None`` if unknown."""
    from plugins.registry import plugin_registry

    parts = [p for p in path.split('/') if p]
    if len(parts) < 2 or parts[0] != 'dashboard':
        return None
    if parts[1] == 'apps' and len(parts) >= 3:
        cand = parts[2]
        return cand if plugin_registry.is_active(cand) else None
    return _segment_plugin_map().get(parts[1])


def track_dashboard_hit(request) -> dict:
    """Context processor: count a dashboard visit against its owning plugin."""
    try:
        path = getattr(request, 'path', '') or ''
        if path.startswith('/dashboard/'):
            plugin = resolve_plugin(path)
            if plugin:
                _incr(plugin, 'dashboard')
    except Exception:  # noqa: BLE001 — never break a render
        logger.debug('feature_adoption: dashboard tracking failed', exc_info=True)
    return {}


# ---------------------------------------------------------------------------
# Agent-tool surface — TOOL_CALLING filter subscriber
# ---------------------------------------------------------------------------


def track_agent_tool(value, tool: str = '', **kwargs):
    """Filter subscriber: count a tool call by its (active-plugin) prefix.

    A no-op transform — returns ``value`` unchanged so the tool call proceeds.
    """
    try:
        prefix = (tool or '').split('.')[0]
        if prefix:
            from plugins.registry import plugin_registry

            if plugin_registry.is_active(prefix):
                _incr(prefix, 'agent_tool')
    except Exception:  # noqa: BLE001 — never break a tool call
        logger.debug('feature_adoption: agent-tool tracking failed', exc_info=True)
    return value


# ---------------------------------------------------------------------------
# Flush
# ---------------------------------------------------------------------------


def flush_counters(days_back: int = 1) -> int:
    """Drain today's (and recent) cache counters into ``FeatureUsageDay``.

    Additive + idempotent: reads then deletes each counter, folding the delta
    into the row with ``F('count') + delta``, so running hourly accumulates
    correctly. Returns the number of (day, plugin, surface) cells flushed.
    """
    from django.db.models import F

    from plugins.installed.feature_adoption.models import FeatureUsageDay

    today = timezone.now().date()
    days = [today - timedelta(days=n) for n in range(days_back + 1)]
    flushed = 0
    for day in days:
        dkey = _dirty_key(day)
        dirty = cache.get(dkey) or set()
        if not dirty:
            continue
        for tag in dirty:
            plugin, _, surface = tag.partition('|')
            key = _counter_key(day, plugin, surface)
            delta = cache.get(key)
            if not delta:
                continue
            cache.delete(key)
            obj, created = FeatureUsageDay.objects.get_or_create(
                day=day, plugin=plugin, surface=surface, defaults={'count': delta}
            )
            if not created:
                FeatureUsageDay.objects.filter(pk=obj.pk).update(count=F('count') + delta)
            flushed += 1
        cache.delete(dkey)
    return flushed


# ---------------------------------------------------------------------------
# Health score
# ---------------------------------------------------------------------------


def compute_health(
    *,
    plugins_used: int,
    plugins_enabled: int,
    agent_calls: int,
    days_since_dashboard: int | None,
) -> dict:
    """Pure install-health score (0–100) from three components.

    breadth (40) = share of enabled plugins used in the window;
    agent (30)   = tool-call volume, capped at ``AGENT_CAP``;
    freshness (30) = dashboard recency, linear decay over ``FRESH_WINDOW`` days.
    """
    enabled = max(1, plugins_enabled)
    breadth = round(BREADTH_PTS * min(1.0, plugins_used / enabled))
    agent = round(AGENT_PTS * min(1.0, agent_calls / AGENT_CAP)) if AGENT_CAP else 0
    if days_since_dashboard is None:
        fresh = 0
    else:
        fresh = round(FRESH_PTS * max(0.0, 1 - days_since_dashboard / FRESH_WINDOW))
    return {
        'score': breadth + agent + fresh,
        'components': {'breadth': breadth, 'agent': agent, 'freshness': fresh},
    }


def install_health() -> dict:
    """Install-health score computed from the last 30 days of ``FeatureUsageDay``."""
    from django.db.models import Sum

    from plugins.installed.feature_adoption.models import FeatureUsageDay
    from plugins.registry import plugin_registry

    today = timezone.now().date()
    since30 = today - timedelta(days=30)
    enabled = len(plugin_registry.active_plugins())
    rows30 = FeatureUsageDay.objects.filter(day__gte=since30)
    used = rows30.values('plugin').distinct().count()
    agent_calls = rows30.filter(surface='agent_tool').aggregate(n=Sum('count'))['n'] or 0
    last = (
        FeatureUsageDay.objects.filter(surface='dashboard')
        .order_by('-day')
        .values_list('day', flat=True)
        .first()
    )
    days_since = (today - last).days if last else None
    return compute_health(
        plugins_used=used,
        plugins_enabled=enabled,
        agent_calls=agent_calls,
        days_since_dashboard=days_since,
    )


# ---------------------------------------------------------------------------
# Adoption matrix (dashboard data)
# ---------------------------------------------------------------------------


def adoption_matrix(days: int = 90) -> dict:
    """Per-plugin usage over 7/30/90-day windows + a daily series for sparklines.

    Also returns ``never_used`` — active plugins with no usage in the window,
    i.e. deprecation candidates.
    """
    from plugins.installed.feature_adoption.models import FeatureUsageDay
    from plugins.registry import plugin_registry

    today = timezone.now().date()
    start = today - timedelta(days=days - 1)
    d7 = today - timedelta(days=6)
    d30 = today - timedelta(days=29)

    per_plugin: dict[str, dict] = {}
    for row in FeatureUsageDay.objects.filter(day__gte=start):
        agg = per_plugin.setdefault(row.plugin, {'u7': 0, 'u30': 0, 'u90': 0, 'series': {}})
        agg['u90'] += row.count
        if row.day >= d30:
            agg['u30'] += row.count
        if row.day >= d7:
            agg['u7'] += row.count
        agg['series'][row.day] = agg['series'].get(row.day, 0) + row.count

    span = [start + timedelta(days=i) for i in range(days)]
    rows = []
    for plugin, agg in sorted(per_plugin.items(), key=lambda kv: -kv[1]['u30']):
        rows.append(
            {
                'plugin': plugin,
                'u7': agg['u7'],
                'u30': agg['u30'],
                'u90': agg['u90'],
                'series': [agg['series'].get(d, 0) for d in span],
            }
        )

    used = set(per_plugin)
    never_used = sorted(p.name for p in plugin_registry.active_plugins() if p.name not in used)
    return {'rows': rows, 'never_used': never_used}


# ---------------------------------------------------------------------------
# DASHBOARD_KPIS contribution
# ---------------------------------------------------------------------------


def dashboard_kpis(value, **kwargs):
    """Append the install-health tile to the dashboard KPI row."""
    try:
        health = install_health()
        value.append(
            {
                'label': 'Install health',
                'value': f'{health["score"]}/100',
                'delta': '',
                'trend': 'flat',
                'icon': 'activity',
                'series': [],
                'hint': 'Breadth of plugins used, agent activity, and dashboard recency (last 30d).',
            }
        )
    except Exception:  # noqa: BLE001
        logger.debug('feature_adoption: kpi tile failed', exc_info=True)
    return value
