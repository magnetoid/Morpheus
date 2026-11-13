"""Core Web Vitals summary — p75 per metric over the last 28 days of field readings.

Public because two surfaces consume it: the SEO dashboard's CWV card (renders it
directly) and the Morpheus Brain aggregator (core/brain/signals.py, through the
BRAIN_SIGNALS filter). The readings live in ``seo.WebVitalSample``
(``plugins/installed/seo/web_vitals.py``).
"""

from __future__ import annotations

from contextlib import suppress


def cwv_summary() -> dict:
    """p75 of LCP (seconds), INP (milliseconds) and CLS over Google's 28-day
    window, the threshold Google uses to decide pass or fail, plus the number of
    readings. Fail-soft: a store without the table yet shows no numbers."""
    out = {'lcp': None, 'inp': None, 'cls': None, 'samples': 0}
    with suppress(Exception):
        from plugins.installed.seo.web_vitals import summary  # noqa: PLC0415

        out = summary()
    return out
