"""Hide the store from search engines until it launches.

One switch, ``hide_until_launch`` (Settings → SEO), read by everything that
invites a crawler: the page head (``noindex, nofollow``), the sitemaps (empty),
robots.txt (no ``Sitemap:`` line — crawling stays allowed, so the noindex is
seen and an already-indexed URL drops out), the AI discovery files (404) and
IndexNow (no ping).
"""

from __future__ import annotations


def hidden_until_launch() -> bool:
    """True while the merchant keeps the store out of search engines.

    Read fresh: the config cache is per process, and the merchant flips the
    switch in one worker while every other one must follow at once.
    """
    from plugins.registry import app_registry

    seo = app_registry.get('seo')
    if seo is None:
        return False
    seo.invalidate_config_cache()
    return bool(seo.get_config_value('hide_until_launch', False))
