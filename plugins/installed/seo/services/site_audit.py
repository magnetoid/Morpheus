"""Site-wide SEO findings — the classes of defect a per-product audit cannot see.

`audit.py` scores one product at a time, which catches a thin description but
is blind to everything that only exists BETWEEN pages: two URLs sharing a
title, a sitemap inviting a crawler to a redirect, a bilingual store emitting
no hreflang. Those are the defects that cost the most traffic and they are the
ones a merchant has no way to find — the Sep 2026 audit of a live store found
all three, and every one of them rendered as perfectly valid markup.

**These checks read what a page RENDERS**, not what a column holds. That
distinction has its own landmine in CLAUDE.md: `seo_gap` scanned columns, got
the fallback chain wrong, and reported 648 products of debt no healer could
repair while missing real gaps. So this fetches each URL in the sitemap through
the real stack and parses the head that comes back.

That costs a full render per URL, so it **never runs in a request**. It runs
from `manage.py seo_site_audit` or the nightly beat task, and the dashboard
reads the cached result. Running it inline would also re-enter the middleware
stack from inside a live request, which is its own kind of trouble.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field

from django.core.cache import cache

logger = logging.getLogger('morpheus.seo.site_audit')

CACHE_KEY = 'seo:site_audit:v1'
CACHE_TTL = 60 * 60 * 26  # outlive a daily run, so a failed night still shows

# Severity drives ordering and the score penalty. Three levels, because a
# merchant triaging their own store will not rank five.
CRITICAL, WARNING, NOTICE = 'critical', 'warning', 'notice'
_PENALTY = {CRITICAL: 12, WARNING: 5, NOTICE: 2}

_TITLE_RE = re.compile(r'<title[^>]*>(.*?)</title>', re.I | re.S)
_DESC_RE = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', re.I | re.S
)
_ROBOTS_RE = re.compile(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\'](.*?)["\']', re.I | re.S)
_CANONICAL_RE = re.compile(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'](.*?)["\']', re.I)
_H1_RE = re.compile(r'<h1\b', re.I)
_HREFLANG_RE = re.compile(r'hreflang=["\']([^"\']+)["\']', re.I)
_JSONLD_RE = re.compile(r'application/ld\+json', re.I)
_TAG_RE = re.compile(r'<[^>]+>')

TITLE_MIN, TITLE_MAX = 30, 60
DESC_MIN, DESC_MAX = 70, 160
THIN_WORDS = 300


@dataclass
class Finding:
    code: str
    severity: str
    title: str
    why: str
    count: int = 0
    examples: list[str] = field(default_factory=list)
    fix_label: str = ''
    fix_url: str = ''

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class PageFacts:
    """What one URL actually returned. Everything else is derived from these."""

    path: str
    status: int
    title: str = ''
    description: str = ''
    robots: str = ''
    canonical: str = ''
    h1_count: int = 0
    hreflangs: list[str] = field(default_factory=list)
    has_jsonld: bool = False
    words: int = 0
    redirect_to: str = ''


def _facts(client, path: str, host: str) -> PageFacts:
    """Fetch one URL through the real stack and read its head.

    `follow=False` on purpose: a sitemap URL that REDIRECTS is itself the
    finding, and following it would hide exactly what we are looking for.
    """
    try:
        response = client.get(path, HTTP_HOST=host)
    except Exception as e:  # noqa: BLE001 — one bad page must not end the audit
        logger.warning('site_audit: %s raised %s', path, e)
        return PageFacts(path=path, status=0)

    status = response.status_code
    if 300 <= status < 400:
        return PageFacts(path=path, status=status, redirect_to=response.get('Location', ''))
    if status != 200:
        return PageFacts(path=path, status=status)

    try:
        html = response.content.decode(response.charset or 'utf-8', errors='ignore')
    except Exception:  # noqa: BLE001
        return PageFacts(path=path, status=status)

    body = html.split('</head>', 1)[-1]
    return PageFacts(
        path=path,
        status=status,
        title=_first(_TITLE_RE, html),
        description=_first(_DESC_RE, html),
        robots=_first(_ROBOTS_RE, html),
        canonical=_first(_CANONICAL_RE, html),
        h1_count=len(_H1_RE.findall(body)),
        hreflangs=_HREFLANG_RE.findall(html),
        has_jsonld=bool(_JSONLD_RE.search(html)),
        words=len(_TAG_RE.sub(' ', body).split()),
    )


def _first(pattern, html: str) -> str:
    match = pattern.search(html)
    return re.sub(r'\s+', ' ', match.group(1)).strip() if match else ''


def _paths(limit: int | None) -> list[str]:
    """Every URL the store publishes, as site-relative paths."""
    from plugins.installed.seo.services.sitemaps import iter_sitemap_entries

    seen: list[str] = []
    for entry in iter_sitemap_entries():
        loc = (entry or {}).get('loc') or ''
        path = '/' + loc.split('/', 3)[3] if loc.count('/') > 2 else '/'
        if path not in seen:
            seen.append(path)
        if limit and len(seen) >= limit:
            break
    return seen


def collect(*, limit: int | None = None) -> dict:
    """Crawl the sitemap in-process and return findings + a score.

    Returns a plain dict so it can be cached and rendered without the models
    layer — this is derived data, recomputable at any time, and giving it a
    table would mean a migration for something that has no history worth
    keeping.
    """
    from django.conf import settings
    from django.test import Client
    from django.utils import timezone

    from core.utils.site import site_base_url

    host = (site_base_url() or '').split('//')[-1].strip('/') or 'testserver'
    # The audit fetches its own site, so the host must be one ALLOWED_HOSTS
    # accepts or every page comes back 400 and the report reads as a dead store.
    allowed = set(getattr(settings, 'ALLOWED_HOSTS', []) or [])
    if host not in allowed and '*' not in allowed:
        host = next((h for h in allowed if h and not h.startswith('.')), 'testserver')

    client = Client()
    pages = [_facts(client, path, host) for path in _paths(limit)]
    findings = _analyse(pages)
    score = max(0, 100 - sum(_PENALTY.get(f.severity, 0) for f in findings))
    return {
        'generated_at': timezone.now().isoformat(),
        'pages_checked': len(pages),
        'score': score,
        'findings': [f.as_dict() for f in findings],
        'coverage': _coverage(pages),
    }


def _analyse(pages: list[PageFacts]) -> list[Finding]:  # noqa: PLR0912 — a linear check list
    """Turn page facts into findings, most severe first."""
    from django.conf import settings

    ok = [p for p in pages if p.status == 200]
    out: list[Finding] = []

    def add(code, severity, title, why, matches, fix_label='', fix_url=''):
        if not matches:
            return
        out.append(
            Finding(
                code=code,
                severity=severity,
                title=title,
                why=why,
                count=len(matches),
                examples=sorted(matches)[:5],
                fix_label=fix_label,
                fix_url=fix_url,
            )
        )

    add(
        'sitemap_redirect',
        CRITICAL,
        'Sitemap lists URLs that redirect',
        'You are inviting crawlers to a page that is not there. Google reports '
        'these as "Page with redirect" and excludes them, and the crawl budget '
        'spent reaching them buys nothing.',
        [p.path for p in pages if 300 <= p.status < 400],
        'Review redirects',
        '/dashboard/seo/redirects/',
    )
    add(
        'sitemap_error',
        CRITICAL,
        'Sitemap lists URLs that fail',
        'A sitemap URL returning an error tells Google the sitemap is stale, '
        'which reduces how much it trusts the rest of it.',
        [f'{p.path} → {p.status}' for p in pages if p.status and p.status >= 400],
        'See 404 log',
        '/dashboard/seo/not-found/',
    )
    add(
        'sitemap_noindex',
        CRITICAL,
        'Pages ask not to be indexed while sitting in the sitemap',
        'Two contradictory instructions about the same URL. The sitemap says '
        '"index this", the page says "do not" — so the page is dropped and the '
        'sitemap loses credibility.',
        [p.path for p in ok if 'noindex' in p.robots.lower()],
        'Review index rules',
        '/dashboard/seo/rules/',
    )
    add(
        'missing_title',
        CRITICAL,
        'Pages with no title',
        'The title is the single strongest on-page signal and the clickable '
        'line in every result. Without one Google invents one.',
        [p.path for p in ok if not p.title],
        'Bulk-edit meta',
        '/dashboard/seo/bulk-meta/',
    )
    add(
        'missing_description',
        WARNING,
        'Pages with no meta description',
        'Google writes its own snippet from the page when none is supplied, '
        'and it rarely picks the sentence you would have.',
        [p.path for p in ok if not p.description],
        'Bulk-edit meta',
        '/dashboard/seo/bulk-meta/',
    )

    for label, code, attr in (
        ('title', 'duplicate_title', 'title'),
        ('meta description', 'duplicate_description', 'description'),
    ):
        groups: dict[str, list[str]] = {}
        for page in ok:
            value = getattr(page, attr)
            if value:
                groups.setdefault(value, []).append(page.path)
        dupes = [
            f'{paths[0]} + {len(paths) - 1} more — "{text[:60]}"'
            for text, paths in groups.items()
            if len(paths) > 1
        ]
        add(
            code,
            WARNING,
            f'Pages sharing a {label}',
            f'Two pages with the same {label} compete with each other for the '
            'same query, and Google picks one — usually not the one you would.',
            dupes,
            'Bulk-edit meta',
            '/dashboard/seo/bulk-meta/',
        )

    add(
        'multiple_h1',
        WARNING,
        'Pages with more than one H1',
        'The H1 states what the page is about. Two of them split that signal, '
        'and the second is usually a template artefact rather than a heading '
        'anyone meant to write.',
        [f'{p.path} ({p.h1_count} H1s)' for p in ok if p.h1_count > 1],
    )
    add(
        'missing_canonical',
        WARNING,
        'Pages with no canonical link',
        'Without one, any URL that reaches this page — a tracking parameter, a '
        'trailing slash — can be indexed as a separate copy.',
        [p.path for p in ok if not p.canonical],
    )

    languages = [c for c, _ in (getattr(settings, 'LANGUAGES', None) or [])]
    if len(languages) > 1:
        add(
            'hreflang_missing',
            WARNING,
            'Translated pages do not declare their alternates',
            f'This store serves {len(languages)} languages, but these pages emit '
            'no hreflang. Google has to guess that the two trees are the same '
            'content, and it usually picks one and treats the other as a '
            'duplicate — so your translation competes with you instead of '
            'reaching a new audience.',
            [p.path for p in ok if not p.hreflangs],
        )

    add(
        'thin_content',
        WARNING,
        f'Pages under {THIN_WORDS} words',
        'Thin pages are the first thing a quality review down-ranks, and they '
        'give an AI answer engine nothing worth quoting.',
        [f'{p.path} ({p.words} words)' for p in ok if 0 < p.words < THIN_WORDS],
    )
    add(
        'no_structured_data',
        NOTICE,
        'Pages with no structured data',
        'Structured data is how a page becomes a rich result and how AI search '
        'reads it as an entity rather than prose.',
        [p.path for p in ok if not p.has_jsonld],
        'Schema editor',
        '/dashboard/seo/schema/',
    )
    add(
        'title_length',
        NOTICE,
        f'Titles outside {TITLE_MIN}–{TITLE_MAX} characters',
        'Long titles are cut off in results and the end is lost; very short '
        'ones waste the most valuable line you get.',
        [
            f'{p.path} ({len(p.title)})'
            for p in ok
            if p.title and not TITLE_MIN <= len(p.title) <= TITLE_MAX
        ],
        'Bulk-edit meta',
        '/dashboard/seo/bulk-meta/',
    )
    add(
        'description_length',
        NOTICE,
        f'Descriptions outside {DESC_MIN}–{DESC_MAX} characters',
        'Over the limit the actionable end of the sentence is truncated away; '
        'under it you are leaving pixels on the table.',
        [
            f'{p.path} ({len(p.description)})'
            for p in ok
            if p.description and not DESC_MIN <= len(p.description) <= DESC_MAX
        ],
        'Bulk-edit meta',
        '/dashboard/seo/bulk-meta/',
    )

    order = {CRITICAL: 0, WARNING: 1, NOTICE: 2}
    out.sort(key=lambda f: (order.get(f.severity, 9), -f.count))
    return out


def _coverage(pages: list[PageFacts]) -> list[dict]:
    """What share of live pages carries each head element."""
    ok = [p for p in pages if p.status == 200]
    total = len(ok) or 1
    checks = (
        ('Title', lambda p: bool(p.title)),
        ('Description', lambda p: bool(p.description)),
        ('Canonical', lambda p: bool(p.canonical)),
        ('One H1', lambda p: p.h1_count == 1),
        ('Structured data', lambda p: p.has_jsonld),
        ('hreflang', lambda p: bool(p.hreflangs)),
    )
    return [
        {
            'label': label,
            'count': (n := sum(1 for p in ok if test(p))),
            'total': len(ok),
            'pct': int(round(100 * n / total)),
        }
        for label, test in checks
    ]


def cached() -> dict | None:
    """The last stored report, or None when nothing has run yet."""
    try:
        return cache.get(CACHE_KEY)
    except Exception:  # noqa: BLE001 — a cache glitch must not break the page
        return None


def run_and_store(*, limit: int | None = None) -> dict:
    report = collect(limit=limit)
    try:
        cache.set(CACHE_KEY, report, CACHE_TTL)
    except Exception:  # noqa: BLE001
        logger.warning('site_audit: could not cache the report', exc_info=True)
    return report
