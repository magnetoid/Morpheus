"""Core Web Vitals summary — p75 per metric over the last 1000 field beacons.

Public because two surfaces consume it: the SEO dashboard's CWV card (renders it
directly) and the Morpheus Brain aggregator (core/brain/signals.py, through the
BRAIN_SIGNALS filter). It reads only AuditEvent rows (event_type='cwv.report') —
no SEO model of its own, so it stays a thin analytics helper.
"""

from __future__ import annotations

from contextlib import suppress


def cwv_summary() -> dict:
    """Aggregate the last 1000 web-vitals beacon reports into p75 per metric —
    the same threshold Google uses to decide pass/fail. Source: AuditEvent rows
    with event_type='cwv.report'. No new model.

    Units are Google's: LCP in seconds, INP in milliseconds, CLS unitless. The
    web-vitals beacon reports LCP in milliseconds, and the dashboard card,
    which compares it with 2.5 and prints "s", showed "1834.00s" in red."""
    out = {'lcp': None, 'inp': None, 'cls': None, 'samples': 0}
    with suppress(Exception):
        from core.audit.models import AuditEvent

        rows = list(
            AuditEvent.objects.filter(event_type='cwv.report')
            .order_by('-created_at')[:1000]
            .values_list('metadata', flat=True)
        )
        if rows:
            out['samples'] = len(rows)
            for metric_key, metric_name in (('lcp', 'LCP'), ('inp', 'INP'), ('cls', 'CLS')):
                values = sorted(
                    [
                        float(m.get('value') or 0.0)
                        for m in rows
                        if (m or {}).get('metric') == metric_name
                    ]
                )
                if values:
                    p75 = values[int(0.75 * (len(values) - 1))]
                    out[metric_key] = round(p75 / 1000, 2) if metric_key == 'lcp' else p75
    return out
