"""One answer to "is this a person in a browser?" for everything that counts visitors.

On the live stores about nine in ten product-page hits come from crawlers
(Semrush, PetalBot, Applebot, Bing, AI crawlers…). Analytics counted every
non-AI crawler as a visitor, and a server-side GA4 hit cannot be bot-filtered
by Google because it never sees the visitor's user agent — so the check lives
here, once, for analytics and tracking alike. An empty user agent is not a
browser either. The nightly SEO site audit identifies itself as a crawler.
"""

from __future__ import annotations

import re

_CRAWLER_UA = re.compile(
    r'bot|crawl|spider|slurp|preview|monitor|lighthouse|headless|scrap|fetch'
    r'|externalhit|googleother|inspectiontool|mediapartners'
    r'|python|curl|wget|go-http|java/|httpclient|okhttp|axios',
    re.IGNORECASE,
)


def is_crawler_user_agent(user_agent: str | None) -> bool:
    """True for a crawler, preview fetcher, HTTP library or empty user agent."""
    ua = user_agent or ''
    return not ua or _CRAWLER_UA.search(ua) is not None
