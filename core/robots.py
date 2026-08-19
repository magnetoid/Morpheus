"""robots.txt as data — the second half of core's crawl seam.

`core/head.py` made the `<head>` a document so any app could contribute a tag.
robots.txt had the same problem in miniature: the seo app hardcoded

    Disallow: /cart/
    Disallow: /checkout/
    Disallow: /auth/

— four URL shapes it does not own. They belong to `storefront`, whose routes
they are; if a merchant moves checkout, or a plugin adds a private surface of
its own, the only way to keep robots.txt honest was to edit the seo app.

So robots.txt is a **document** too: seo builds one, seeds the paths that are
genuinely its own concern (`/dashboard/`, `/admin/` — chrome, not a plugin's),
fires `SEO_ROBOTS_RULES`, and renders whatever came back. Core defines the
shape and knows nothing about which paths deserve blocking (ADR 0017).

Two deliberate simplifications, both from what robots.txt actually is:

* **A disallow applies to every group.** The rendered file has one group per
  AI crawler plus a `User-agent: *` fallback, and a path that should not be
  crawled should not be crawled by any of them. Per-agent rules are the
  AI-crawler matrix's job, which is seo's own policy, not a contribution.
* **Entries are deduplicated and order is preserved.** Two apps disallowing
  `/checkout/` produce one line, and the file does not reshuffle between
  requests — robots.txt is cached at the edge and a churning body defeats it.
"""

from __future__ import annotations


class RobotsDocument:
    """A mutable description of the rules every crawler group receives.

    Contributors call `disallow()` / `allow()` / `sitemap()`; the renderer
    (`seo.services.crawler_files`) reads the lists back and lays out the groups.
    Nothing here writes robots.txt syntax — a contributor that had to know the
    file format would be back to editing another app's output.
    """

    __slots__ = ('_allow', '_disallow', '_sitemaps')

    def __init__(self) -> None:
        self._disallow: list[str] = []
        self._allow: list[str] = []
        self._sitemaps: list[str] = []

    def disallow(self, path: str) -> None:
        """Block a path or path pattern (`/cart/`, `/*?*sort=`) for every group."""
        _append(self._disallow, path)

    def allow(self, path: str) -> None:
        """Carve an exception out of a broader Disallow (`/cart/summary.json`)."""
        _append(self._allow, path)

    def sitemap(self, url: str) -> None:
        """Advertise a sitemap (or sitemap index) at an absolute URL."""
        _append(self._sitemaps, url)

    @property
    def disallowed(self) -> tuple[str, ...]:
        return tuple(self._disallow)

    @property
    def allowed(self) -> tuple[str, ...]:
        return tuple(self._allow)

    @property
    def sitemaps(self) -> tuple[str, ...]:
        return tuple(self._sitemaps)


def _append(target: list[str], value: str) -> None:
    """Add a trimmed, non-empty, not-already-present value.

    Contributions arrive from several apps that cannot see each other, so
    duplicates are normal rather than a caller error — dropping them here is
    cheaper than every contributor checking first.
    """
    cleaned = (value or '').strip()
    if cleaned and cleaned not in target:
        target.append(cleaned)
