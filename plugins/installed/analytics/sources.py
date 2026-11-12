"""Where a visit came from (v0.158.0).

The visit's first page names its arrival: the tags on its address (``utm_*``,
an ad click id) or else the site that sent it. Each pageview beacon carries
the arrival it would start (``payload['arr']``); the daily roll gives each
visit the arrival of its first page.

Until v0.158.0 a source belonged to the visitor, not the visit: the two-year
analytics cookie kept the referrer of the visitor's first visit, so someone who
first came from Facebook and returned from Google a year later still read as
Facebook.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

#: The channels a visit is filed under, in the order the Sources page lists them.
CHANNELS = (
    ('organic', 'Organic search'),
    ('paid', 'Paid ads'),
    ('social', 'Social'),
    ('email', 'Email'),
    ('ai', 'AI assistants'),
    ('referral', 'Other sites'),
    ('direct', 'Direct'),
    ('unknown', 'Not known'),
)
CHANNEL_LABELS = dict(CHANNELS)

#: Search engines, by the host a result links from.
_SEARCH = (
    (re.compile(r'^(www\.|m\.)?google\.[a-z.]+$'), 'google'),
    (re.compile(r'(^|\.)googlequicksearchbox$'), 'google'),
    (re.compile(r'^(cn\.)?bing\.com$'), 'bing'),
    (re.compile(r'(^|\.)duckduckgo\.com$'), 'duckduckgo'),
    (re.compile(r'(^|\.)search\.yahoo\.[a-z.]+$'), 'yahoo'),
    (re.compile(r'^yandex\.[a-z.]+$'), 'yandex'),
    (re.compile(r'(^|\.)ecosia\.org$'), 'ecosia'),
    (re.compile(r'(^|\.)baidu\.com$'), 'baidu'),
    (re.compile(r'(^|\.)startpage\.com$'), 'startpage'),
    (re.compile(r'(^|\.)qwant\.com$'), 'qwant'),
    (re.compile(r'^search\.brave\.com$'), 'brave'),
    (re.compile(r'(^|\.)naver\.com$'), 'naver'),
    (re.compile(r'(^|\.)seznam\.cz$'), 'seznam'),
)
_ENGINE_NAMES = frozenset(name for _pattern, name in _SEARCH)

#: Social sites, by host (a subdomain matches too).
_SOCIAL = {
    'facebook.com': 'facebook',
    'fb.com': 'facebook',
    'fb.me': 'facebook',
    'messenger.com': 'facebook',
    'instagram.com': 'instagram',
    't.co': 'x',
    'twitter.com': 'x',
    'x.com': 'x',
    'linkedin.com': 'linkedin',
    'lnkd.in': 'linkedin',
    'pinterest.com': 'pinterest',
    'pin.it': 'pinterest',
    'reddit.com': 'reddit',
    'tiktok.com': 'tiktok',
    'youtube.com': 'youtube',
    'youtu.be': 'youtube',
    'threads.net': 'threads',
    'threads.com': 'threads',
    'bsky.app': 'bluesky',
    'vk.com': 'vk',
    't.me': 'telegram',
    'whatsapp.com': 'whatsapp',
    'snapchat.com': 'snapchat',
    'tumblr.com': 'tumblr',
    'quora.com': 'quora',
}
_SOCIAL_NAMES = frozenset(_SOCIAL.values())

#: Webmail, whose links are an email the visitor opened.
_WEBMAIL = {
    'mail.google.com': 'gmail',
    'com.google.android.gm': 'gmail',
    'outlook.live.com': 'outlook',
    'outlook.office.com': 'outlook',
    'outlook.office365.com': 'outlook',
    'mail.yahoo.com': 'yahoo mail',
    'mail.proton.me': 'proton mail',
}

#: Pages a visitor passes through on the way back to the store (paying,
#: signing in): they name no new arrival.
_PASS_THROUGH = {
    'checkout.stripe.com': '',
    'hooks.stripe.com': '',
    'js.stripe.com': '',
    'paypal.com': '',
    'accounts.google.com': '',
    'appleid.apple.com': '',
}

#: Ad click ids a platform adds to its ad links, and the platform.
_PAID_CLICK_IDS = (
    ('gclid', 'google'),
    ('gbraid', 'google'),
    ('wbraid', 'google'),
    ('dclid', 'google'),
    ('msclkid', 'bing'),
    ('ttclid', 'tiktok'),
    ('li_fat_id', 'linkedin'),
    ('twclid', 'x'),
)
#: Click ids a platform adds to every outbound link, ad or not.
_SOCIAL_CLICK_IDS = (('fbclid', 'facebook'), ('igshid', 'instagram'))

_PAID_MEDIUM = re.compile(r'^(.*cp.*|ppc|retargeting|paid.*|display|banner|interstitial)$')
_EMAIL = re.compile(r'^(e[-_ ]?mail|newsletter)$')
_SOCIAL_MEDIUM = re.compile(r'^(social|social[-_ ]?(network|media)|sm|organic[-_ ]?social)$')


def _host(url: str) -> str:
    try:
        host = (urlsplit(url or '').hostname or '').lower()
    except ValueError:
        return ''
    return host.removeprefix('www.')


def _within(host: str, table: dict) -> str | None:
    """The table's name for ``host`` or a domain it is under, else None."""
    for domain, name in table.items():
        if host == domain or host.endswith('.' + domain):
            return name
    return None


def search_engine(host: str) -> str:
    """'google' for a Google results host (or the bare name), '' for any other."""
    if host in _ENGINE_NAMES:
        return host
    for pattern, name in _SEARCH:
        if pattern.search(host):
            return name
    return ''


def _first(query: dict, name: str, size: int) -> str:
    value = query.get(name) or ''
    if isinstance(value, list | tuple):
        value = value[0] if value else ''
    return str(value).strip()[:size]


def _arrival(channel: str, source: str = '', medium: str = '', campaign: str = '') -> dict:
    out = {'ch': channel, 's': source[:80], 'm': medium[:80], 'c': campaign[:120]}
    return {k: v for k, v in out.items() if v}


def classify(referrer: str, query: dict, store_host: str) -> dict:
    """The arrival a page would start a visit with.

    ``{'ch', 's', 'm', 'c'}`` (channel, source, medium, campaign; empty ones
    left out), or ``{}`` when the page was reached from the store itself or
    from a page that hands visitors back to it (a payment page): such a page
    names no arrival.
    """
    from plugins.installed.analytics.services import ai_source_from_referrer  # noqa: PLC0415

    source = _first(query, 'utm_source', 80).lower()
    medium = _first(query, 'utm_medium', 80).lower()
    campaign = _first(query, 'utm_campaign', 120)
    host = _host(referrer)

    ai = (ai_source_from_referrer(f'https://{source}') if source else '') or (
        ai_source_from_referrer(referrer)
    )
    if ai:
        return _arrival('ai', ai, medium or 'ai-assistant', campaign)
    paid = _paid_click(query)
    if paid and not medium:
        # An ad link carries its click id beside a bare ``utm_source=google``,
        # which on its own names a search engine: the click id says it was an ad.
        return _arrival('paid', source or paid, 'cpc', campaign)
    if source or medium:
        return _arrival(_tagged_channel(source, medium), source or host, medium, campaign)
    return _untagged(host, query, campaign, (store_host or '').lower().removeprefix('www.'))


def _tagged_channel(source: str, medium: str) -> str:
    """The channel ``utm_source`` and ``utm_medium`` name (GA4's default rules)."""
    if _PAID_MEDIUM.match(medium):
        return 'paid'
    if _EMAIL.match(medium) or _EMAIL.match(source):
        return 'email'
    if _SOCIAL_MEDIUM.match(medium) or source in _SOCIAL_NAMES or _within(source, _SOCIAL):
        return 'social'
    if medium == 'organic' or search_engine(source):
        return 'organic'
    return 'referral'


def _paid_click(query: dict) -> str:
    """The ad platform whose click id the address carries, else ''."""
    for key, platform in _PAID_CLICK_IDS:
        if query.get(key):
            return platform
    return ''


def _untagged(host: str, query: dict, campaign: str, own: str) -> dict:
    if (own and (host == own or host.endswith('.' + own))) or _within(
        host, _PASS_THROUGH
    ) is not None:
        return {}
    for key, platform in _SOCIAL_CLICK_IDS:
        if query.get(key):
            return _arrival('social', _within(host, _SOCIAL) or platform, 'referral', campaign)
    if not host:
        return _arrival('direct')
    return _referred(host)


def _referred(host: str) -> dict:
    engine = search_engine(host)
    if engine:
        return _arrival('organic', engine, 'organic')
    for table, channel in ((_SOCIAL, 'social'), (_WEBMAIL, 'email')):
        name = _within(host, table)
        if name:
            return _arrival(channel, name, 'referral')
    return _arrival('referral', host, 'referral')
