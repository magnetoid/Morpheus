"""Cross-channel attribution + blended ROAS.

Combines two sources we already have, no new credentials:
  * **ad spend + platform-claimed conversions/revenue** per channel — the daily
    cached `CHANNELS_METRICS` rows (channels:metrics:v1).
  * **real last-touch revenue** per channel — `analytics.revenue_by_source`
    (purchase events grouped by the converting session's utm_source).

The honest insight merchants want: a trustworthy **blended MER** (total store
revenue ÷ total ad spend) alongside each channel's **platform-claimed vs
last-touch** revenue — platforms systematically over-claim, and the gap is the
point. Fail-soft: missing analytics → last-touch columns blank; missing metrics
→ spend blank.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.channels')

# Stable display labels for the eight channels (their plugin names).
_LABELS = {
    'google_shopping': 'Google',
    'meta_commerce': 'Meta',
    'tiktok_commerce': 'TikTok',
    'pinterest_commerce': 'Pinterest',
    'microsoft_commerce': 'Microsoft',
    'amazon_ads': 'Amazon',
    'reddit_ads': 'Reddit',
    'snapchat_commerce': 'Snapchat',
}

# utm_source value (lowercased) → channel plugin name. Covers the common tags an
# ad platform appends; unknown sources fall into "other attributed".
_SOURCE_TO_CHANNEL = {
    'google': 'google_shopping',
    'googleads': 'google_shopping',
    'google_ads': 'google_shopping',
    'gads': 'google_shopping',
    'facebook': 'meta_commerce',
    'meta': 'meta_commerce',
    'fb': 'meta_commerce',
    'instagram': 'meta_commerce',
    'ig': 'meta_commerce',
    'tiktok': 'tiktok_commerce',
    'pinterest': 'pinterest_commerce',
    'microsoft': 'microsoft_commerce',
    'bing': 'microsoft_commerce',
    'amazon': 'amazon_ads',
    'reddit': 'reddit_ads',
    'snapchat': 'snapchat_commerce',
    'snap': 'snapchat_commerce',
}


def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def build_attribution(*, days: int = 30) -> dict:
    """Assemble the blended + per-channel attribution view. Pure reads; safe to
    call on every page load (the underlying ads metrics are daily-cached)."""
    from django.core.cache import cache

    from plugins.installed.channels.tasks import METRICS_CACHE_KEY

    metrics = cache.get(METRICS_CACHE_KEY) or []
    by_name = {m['name']: m for m in metrics if isinstance(m, dict) and m.get('name')}

    rev = {'by_source': {}, 'direct': 0.0, 'total': 0.0}
    try:
        from plugins.installed.analytics.services import revenue_by_source

        rev = revenue_by_source(days=days)
    except Exception as e:  # noqa: BLE001 — analytics optional; degrade gracefully
        logger.debug('channels: revenue_by_source unavailable: %s', e)

    # Fold last-touch revenue onto channels via the utm_source map.
    lasttouch: dict[str, float] = {}
    other_attributed = 0.0
    for src, amt in (rev.get('by_source') or {}).items():
        ch = _SOURCE_TO_CHANNEL.get(src)
        if ch:
            lasttouch[ch] = lasttouch.get(ch, 0.0) + _num(amt)
        else:
            other_attributed += _num(amt)

    rows = []
    total_spend = 0.0
    for name, label in _LABELS.items():
        m = by_name.get(name) or {}
        spend = _num(m.get('spend'))
        lt = round(lasttouch.get(name, 0.0), 2)
        if not spend and not lt:
            continue  # nothing to show for this channel
        total_spend += spend
        rows.append(
            {
                'name': name,
                'label': label,
                'spend': round(spend, 2),
                'conversions': m.get('conversions'),
                'platform_revenue': m.get('revenue'),
                'platform_roas': m.get('roas'),
                'lasttouch_revenue': lt,
                'lasttouch_roas': round(lt / spend, 2) if spend else None,
            }
        )

    rows.sort(key=lambda r: r['spend'], reverse=True)
    total_revenue = round(_num(rev.get('total')), 2)
    return {
        'rows': rows,
        'total_spend': round(total_spend, 2),
        'total_revenue': total_revenue,
        'blended_roas': round(total_revenue / total_spend, 2) if total_spend else None,
        'attributed_revenue': round(sum(lasttouch.values()), 2),
        'other_attributed': round(other_attributed, 2),
        'direct_revenue': round(_num(rev.get('direct')), 2),
        'has_metrics': bool(metrics),
        'has_revenue': total_revenue > 0,
        'days': int(days),
    }
