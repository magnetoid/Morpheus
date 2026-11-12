"""The return window, for every page that states it.

Themes printed "30-day returns" (dot books, Supernatural) as their own copy,
so a merchant who set another window, or none, saw the product page promise
30 days anyway. Contributed with `register_context_processor`, so the value
leaves with the app: a store without returns_portal states no window.
"""

from __future__ import annotations


def return_window(request) -> dict:
    """`return_window_days`: the merchant's window in days, 0 when it takes no returns."""
    from plugins.installed.returns_portal.seo_graph import window_days

    return {'return_window_days': window_days()}
