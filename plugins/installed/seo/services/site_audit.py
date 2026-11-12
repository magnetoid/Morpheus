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

**It also checks what the markup claims (v0.164.0).** A Product node's offer is a
public statement: its price must be printed on the page and be the price the
store charges now (`core.pricing.apply_price_filter`, the seam GraphQL's price
and the cart read), its availability must be inventory's answer (through
`plugins.feed_mapping`, the function the graph uses), and every image it or
`og:image` names must answer 200 with an image. Between pages it finds links to
redirects, redirect chains and sitemap pages nothing links to. Each finding names
the page and what was claimed against what was found.
"""

from __future__ import annotations

import html as _html
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from urllib.parse import unquote, urljoin, urlsplit

from celery.exceptions import SoftTimeLimitExceeded
from django.core.cache import cache

from core.ratelimit import INTERNAL_REQUEST_ENVIRON_KEY

logger = logging.getLogger('morpheus.seo.site_audit')

# A crawler's user agent, so analytics and tracking don't count the audit's
# nightly pass over every page as visitors.
_AUDIT_USER_AGENT = 'MorpheusSiteAudit/1.0 (internal crawler)'

CACHE_KEY = 'seo:site_audit:v1'
CACHE_TTL = 60 * 60 * 26  # outlive a daily run, so a failed night still shows

# Severity drives ordering and the score penalty. Three levels, because a
# merchant triaging their own store will not rank five; INFO is not a defect (work
# still to do, such as translations) and costs the score nothing.
CRITICAL, WARNING, NOTICE, INFO = 'critical', 'warning', 'notice', 'info'
_PENALTY = {CRITICAL: 12, WARNING: 5, NOTICE: 2}
_ORDER = {CRITICAL: 0, WARNING: 1, NOTICE: 2, INFO: 3}

_TITLE_RE = re.compile(r'<title[^>]*>(.*?)</title>', re.I | re.S)
_DESC_RE = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', re.I | re.S
)
_ROBOTS_RE = re.compile(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\'](.*?)["\']', re.I | re.S)
_CANONICAL_RE = re.compile(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'](.*?)["\']', re.I)
_H1_RE = re.compile(r'<h1\b', re.I)
_HREFLANG_RE = re.compile(r'hreflang=["\']([^"\']+)["\']', re.I)
_ALTERNATE_RE = re.compile(
    r'<link[^>]+rel=["\']alternate["\'][^>]*?href=["\']([^"\']+)["\'][^>]*?hreflang=["\']([^"\']+)["\']',
    re.I,
)
_JSONLD_RE = re.compile(r'application/ld\+json', re.I)
_TAG_RE = re.compile(r'<[^>]+>')
_JSONLD_BLOCK_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script\s*>', re.I | re.S
)
_META_TAG_RE = re.compile(r'<meta\b([^>]*)>', re.I)
_LINK_TAG_RE = re.compile(r'<link\b([^>]*)>', re.I)
_ANCHOR_RE = re.compile(r'<a\b([^>]*)>', re.I)
_ATTR_RE = re.compile(r'([^\s=/>"\']+)(?:\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+)))?')
_HTML_LANG_RE = re.compile(r'<html\b[^>]*\blang=["\']([^"\']+)', re.I)
_INVISIBLE_RE = re.compile(r'<(script|style|template)\b.*?</\1\s*>', re.I | re.S)
_COMMENT_RE = re.compile(r'<!--.*?-->', re.S)

TITLE_MIN, TITLE_MAX = 30, 60
DESC_MIN, DESC_MAX = 70, 160
THIN_WORDS = 300

#: Pages kept per finding: the dashboard shows five, Linda's seo.audit_results twenty.
MAX_EXAMPLES = 20
#: A redirect is followed this many hops at most, and never off the store's host.
MAX_HOPS = 5
#: Fetches beyond the sitemap crawl. Each link target not in the sitemap costs a
#: render, so they are capped and the report says when a cap was reached.
MAX_LINK_FETCHES = 400
MAX_PAGINATION_FETCHES = 600
MAX_IMAGE_FETCHES = 2000
#: The extra checks stop starting fetches this long after the run began, so the
#: whole run stays inside the task's 1,800 s soft limit with room to store it.
EXTRA_DEADLINE_S = 1500

# Link targets the crawl never follows: not pages, or not a crawler's to fetch.
_SKIP_LINK_PREFIXES = (
    '/dashboard/',
    '/admin/',
    '/api/',
    '/graphql',
    '/mcp/',
    '/media/',
    '/static/',
    '/img/',
    '/csrf/',
)
_SKIP_SCHEMES = ('#', 'mailto:', 'tel:', 'sms:', 'javascript:', 'data:')

# Re-running the scan: one at a time, and not again within ten minutes.
RUNNING_KEY = 'seo:site_audit:running'
QUEUED_KEY = 'seo:site_audit:queued'
RERUN_AFTER_S = 600
_RUNNING_TTL = 1920  # the task's hard time limit


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
    hreflang_hrefs: list[tuple[str, str]] = field(default_factory=list)
    has_jsonld: bool = False
    words: int = 0
    redirect_to: str = ''
    # What the page's Product nodes claim (`_claims`), and its og:image as declared.
    claims: list[dict] = field(default_factory=list)
    og_image: str = ''
    og_size: tuple[int, int] | None = None
    # Internal paths it links to (query dropped), and its rel=next page.
    links: list[str] = field(default_factory=list)
    next_href: str = ''


@dataclass
class NotFoundFacts:
    """How the store answers a URL that cannot exist."""

    path: str
    status: int
    canonical: str = ''
    hreflangs: list[str] = field(default_factory=list)
    has_jsonld: bool = False


def _facts(client, path: str, host: str) -> PageFacts:
    """Fetch one URL through the real stack and read its head.

    `follow=False` on purpose: a sitemap URL that REDIRECTS is itself the
    finding, and following it would hide exactly what we are looking for.
    """
    try:
        # `secure=True` is load-bearing. Production sets SECURE_SSL_REDIRECT, so
        # a plain in-process request is 301'd to https by SecurityMiddleware
        # before it reaches a view — and this audit would then report EVERY url
        # in the sitemap as a redirect. Dev has the flag off, so no local test
        # can see it; the first prod run reported 59 of 59 pages critical.
        # The internal marker keeps the storefront rate limiter from 429ing the
        # audit (it is one anonymous client fetching hundreds of pages a
        # minute), and the user agent tells analytics this is not a visitor.
        response = client.get(
            path,
            HTTP_HOST=host,
            HTTP_USER_AGENT=_AUDIT_USER_AGENT,
            secure=True,
            **{INTERNAL_REQUEST_ENVIRON_KEY: True},
        )
    except SoftTimeLimitExceeded:
        raise  # the task's time budget is spent — stop, don't crawl on to the hard kill
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
    return page_facts(path, status, html, host)


def page_facts(path: str, status: int, html: str, host: str) -> PageFacts:
    """Read one rendered page: its head, what its markup claims, and its links."""
    head = html.split('</head>', 1)[0]
    body = html.split('</head>', 1)[-1]
    hosts = _own_hosts(host)
    og_image, og_size = _og_image(head)
    return PageFacts(
        path=path,
        status=status,
        title=_first(_TITLE_RE, html),
        description=_first(_DESC_RE, html),
        robots=_first(_ROBOTS_RE, html),
        canonical=_first(_CANONICAL_RE, html),
        h1_count=len(_H1_RE.findall(body)),
        hreflangs=_HREFLANG_RE.findall(html),
        hreflang_hrefs=[
            (code, href.replace('&amp;', '&')) for href, code in _ALTERNATE_RE.findall(html)
        ],
        has_jsonld=bool(_JSONLD_RE.search(html)),
        words=len(_TAG_RE.sub(' ', body).split()),
        claims=_claims(html, _visible_text(body), _first(_HTML_LANG_RE, html)),
        og_image=og_image,
        og_size=og_size,
        links=_links(body, path, host, hosts),
        next_href=_next_href(head, path, host, hosts),
    )


# ── Reading a page: attributes, links, the graph's Product claims ────────────


def _attrs(raw: str) -> dict[str, str]:
    """A tag's attributes, names lower-cased and values unescaped."""
    out: dict[str, str] = {}
    for name, dq, sq, bare in _ATTR_RE.findall(raw or ''):
        out.setdefault(name.lower(), _html.unescape(dq or sq or bare or ''))
    return out


def _own_hosts(host: str) -> set[str]:
    from core.utils.site import site_base_url

    return {h for h in (host, urlsplit(site_base_url() or '').netloc) if h}


def _strip_language(path: str) -> str:
    from django.conf import settings

    codes = {c.lower() for c, _ in (getattr(settings, 'LANGUAGES', None) or [])}
    parts = path.split('/', 2)
    if len(parts) > 2 and parts[1].lower() in codes:
        return '/' + parts[2]
    return path


def _skipped_path(path: str) -> bool:
    from plugins.installed.seo.pages.resolve import _is_private

    bare = _strip_language(path)
    return (
        _is_private(path)
        or _is_private(bare)
        or path.startswith(_SKIP_LINK_PREFIXES)
        or bare.startswith(_SKIP_LINK_PREFIXES)
    )


def _internal_url(href: str, page_path: str, host: str, hosts: set[str], *, keep_query=False):
    """The site-relative URL an href names on this store, or '' (another host, a
    mailto, a private or machine path)."""
    href = (href or '').strip()
    if not href or href.lower().startswith(_SKIP_SCHEMES):
        return ''
    try:
        parts = urlsplit(urljoin(f'https://{host}{page_path}', href))
    except ValueError:  # href="http://[" in a page's own copy: skip it, scan the rest
        return ''
    if parts.scheme not in ('http', 'https') or (parts.netloc and parts.netloc not in hosts):
        return ''
    path = parts.path or '/'
    if _skipped_path(path):
        return ''
    return path + (f'?{parts.query}' if keep_query and parts.query else '')


def _links(body: str, page_path: str, host: str, hosts: set[str]) -> list[str]:
    """Internal paths the page links to, the way a crawler follows them.

    A language switcher (an anchor carrying hreflang or lang), a download and a
    nofollow link are not followed; the query is dropped, so a listing's filter
    and sort links count as links to the listing.
    """
    out: list[str] = []
    for raw in _ANCHOR_RE.findall(body):
        attrs = _attrs(raw)
        if 'hreflang' in attrs or 'lang' in attrs or 'download' in attrs:
            continue
        if 'nofollow' in attrs.get('rel', '').lower().split():
            continue
        target = _internal_url(attrs.get('href', ''), page_path, host, hosts)
        if target and target not in out:
            out.append(target)
    return out


def _next_href(head: str, page_path: str, host: str, hosts: set[str]) -> str:
    for raw in _LINK_TAG_RE.findall(head):
        attrs = _attrs(raw)
        if 'next' in attrs.get('rel', '').lower().split():
            return _internal_url(attrs.get('href', ''), page_path, host, hosts, keep_query=True)
    return ''


def _og_image(head: str) -> tuple[str, tuple[int, int] | None]:
    """og:image and the width and height the page declares for it."""
    image, width, height = '', None, None
    for raw in _META_TAG_RE.findall(head):
        attrs = _attrs(raw)
        prop, content = attrs.get('property', '').lower(), attrs.get('content', '')
        if prop == 'og:image' and not image:
            image = content
        elif prop == 'og:image:width' and width is None:
            width = _int(content)
        elif prop == 'og:image:height' and height is None:
            height = _int(content)
    return image, ((width, height) if width and height else None)


def _int(value) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _norm(text: str) -> str:
    for space in ('\xa0', '\u202f', '\u2009', '\u2007'):
        text = text.replace(space, ' ')
    return re.sub(r'\s+', ' ', text).strip()


def _visible_text(body: str) -> str:
    """What a visitor can read: no scripts, styles, templates, comments or tags."""
    text = _INVISIBLE_RE.sub(' ', _COMMENT_RE.sub(' ', body))
    return _norm(_html.unescape(_TAG_RE.sub(' ', text)))


def _graph_nodes(html: str) -> list[dict]:
    nodes: list[dict] = []
    for raw in _JSONLD_BLOCK_RE.findall(html):
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            continue
        for item in data if isinstance(data, list) else [data]:
            if not isinstance(item, dict):
                continue
            graph = item.get('@graph')
            nodes.extend(
                n for n in (graph if isinstance(graph, list) else [item]) if isinstance(n, dict)
            )
    return nodes


def _types(node: dict) -> set[str]:
    kind = node.get('@type')
    if isinstance(kind, str):
        return {kind}
    return {k for k in kind if isinstance(k, str)} if isinstance(kind, list) else set()


def _decimal(value) -> Decimal | None:
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def _image_urls(value) -> list[str]:
    items = value if isinstance(value, list) else [value]
    out = []
    for item in items:
        url = item.get('contentUrl') or item.get('url') if isinstance(item, dict) else item
        if isinstance(url, str) and url.strip() and url.strip() not in out:
            out.append(url.strip())
    return out


def _claims(html: str, text: str, lang: str) -> list[dict]:
    """What each Product node on the page claims: its offer and its images.

    A ProductGroup's own node carries no offer (each variant has one); its
    variants are claims too, matched to their owner by SKU. Only a page's own
    product is checked against the visible text: a variant's price is often shown
    only once it is picked.
    """
    out: list[dict] = []
    for node in _graph_nodes(html):
        if not _types(node) & {'Product', 'ProductGroup'}:
            continue
        out.append(_claim(node, text, lang, main=True))
        for member in node.get('hasVariant') or []:
            if isinstance(member, dict) and 'Product' in _types(member):
                out.append(_claim(member, text, lang, main=False))
    return out


def _claim(node: dict, text: str, lang: str, *, main: bool) -> dict:
    offers = node.get('offers')
    offer = next(
        (
            o
            for o in (offers if isinstance(offers, list) else [offers])
            if isinstance(o, dict) and o.get('price') not in (None, '')
        ),
        {},
    )
    price = _decimal(offer.get('price'))
    currency = str(offer.get('priceCurrency') or '').upper()
    claim = {
        'name': str(node.get('name') or ''),
        'sku': str(node.get('sku') or ''),
        'url': str(node.get('url') or '') if main else '',
        'price': f'{price:.2f}' if price is not None else '',
        'currency': currency,
        'availability': str(offer.get('availability') or ''),
        'images': _image_urls(node.get('image')),
        'main': main,
    }
    if main and price is not None:
        claim['shown'] = _price_shown(price, currency, text, lang)
    return claim


def _price_forms(amount: Decimal, currency: str, lang: str) -> set[str]:
    """The ways the page may print ``amount``: through `|money` in the page's
    language and the store's, and as a plain decimal (either separator)."""
    from django.conf import settings
    from django.utils import translation

    from core.templatetags.morph import money_filter

    plain = f'{amount:.2f}'
    forms = {plain, plain.replace('.', ',')}
    for code in dict.fromkeys(c for c in (lang, settings.LANGUAGE_CODE) if c):
        try:
            with translation.override(code):
                forms.add(
                    _norm(str(money_filter({'amount': plain, 'currency': currency or 'USD'})))
                )
        except Exception:  # noqa: BLE001, S112 — an odd language code: the other forms stand
            continue
    return {f for f in forms if f}


def _price_shown(amount: Decimal, currency: str, text: str, lang: str) -> bool:
    return any(
        re.search(r'(?<![\d.,])' + re.escape(form) + r'(?!\d)', text)
        for form in _price_forms(amount, currency, lang)
    )


def _probe_missing(client, host: str) -> NotFoundFacts:
    """Ask for a URL that cannot exist and read what comes back.

    A store must answer 404, and the 404 page must not name a URL: the October
    crawl found every store's 404 carrying a canonical, hreflang alternates and
    a WebPage graph for the dead address beside a correct `noindex`.
    """
    import secrets

    path = f'/morpheus-audit-missing-{secrets.token_hex(6)}/'
    try:
        response = client.get(
            path,
            HTTP_HOST=host,
            HTTP_USER_AGENT=_AUDIT_USER_AGENT,
            secure=True,
            **{INTERNAL_REQUEST_ENVIRON_KEY: True},
        )
    except SoftTimeLimitExceeded:
        raise
    except Exception as e:  # noqa: BLE001 — a probe failure is not a finding
        logger.warning('site_audit: not-found probe raised %s', e)
        return NotFoundFacts(path=path, status=0)
    head = ''
    if 'html' in (response.get('Content-Type') or ''):
        html = response.content.decode(response.charset or 'utf-8', errors='ignore')
        head = html.split('</head>', 1)[0]
    return NotFoundFacts(
        path=path,
        status=response.status_code,
        canonical=_first(_CANONICAL_RE, head),
        hreflangs=_HREFLANG_RE.findall(head),
        has_jsonld=bool(_JSONLD_RE.search(head)),
    )


def _not_found_findings(probe: NotFoundFacts) -> list[Finding]:
    """Findings about how the store answers a missing page."""
    out: list[Finding] = []
    if probe.status == 200:
        out.append(
            Finding(
                code='missing_pages_answer_200',
                severity=CRITICAL,
                title='Pages that do not exist answer "200 OK"',
                why=(
                    'Every mistyped or retired address looks like a real page, so search '
                    'engines index an unbounded set of duplicates and report the site as full '
                    'of soft 404s.'
                ),
                count=1,
                examples=[probe.path],
            )
        )
    elif probe.status == 404 and (probe.canonical or probe.hreflangs or probe.has_jsonld):
        out.append(
            Finding(
                code='error_page_names_a_url',
                severity=WARNING,
                title='The "page not found" page names a URL',
                why=(
                    'A 404 should carry a title and "noindex" and nothing else. A canonical, '
                    'hreflang alternates or structured data on it describe a page that does not '
                    'exist, and contradict the status code.'
                ),
                count=1,
                examples=[probe.path],
            )
        )
    return out


def _first(pattern, html: str) -> str:
    match = pattern.search(html)
    return re.sub(r'\s+', ' ', match.group(1)).strip() if match else ''


def _paths(limit: int | None) -> list[str]:
    """Every URL the store publishes, as site-relative paths.

    The MERGED corpus, not `iter_sitemap_entries()`. The native generator
    yields only what seo knows how to build itself; a vertical's routes arrive
    through the `SITEMAP_URLS` filter. Auditing the native list alone checked
    59 of Montenegro's 343 URLs and silently skipped every booking, stay, place
    and event — the commercial catalogue, which is precisely what an SEO report
    exists to cover.
    """
    from plugins.installed.seo.services.sitemaps import _merged_sitemap_entries

    seen: list[str] = []
    for entry in _merged_sitemap_entries():
        loc = (entry or {}).get('loc') or ''
        path = '/' + loc.split('/', 3)[3] if loc.count('/') > 2 else '/'
        if path not in seen:
            seen.append(path)
        if limit and len(seen) >= limit:
            break
    return seen


def _get(client, path: str, host: str):
    """One in-process request the way the crawl makes them (see `_facts`)."""
    return client.get(
        path,
        HTTP_HOST=host,
        HTTP_USER_AGENT=_AUDIT_USER_AGENT,
        secure=True,
        **{INTERNAL_REQUEST_ENVIRON_KEY: True},
    )


class _Capped(Exception):
    """A fetch cap or the extra checks' deadline was reached."""


def collect(*, limit: int | None = None) -> dict:  # noqa: PLR0915 — one run, its phases in order
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

    started = time.monotonic()
    host = (site_base_url() or '').split('//')[-1].strip('/') or 'testserver'
    # The audit fetches its own site, so the host must be one ALLOWED_HOSTS
    # accepts or every page comes back 400 and the report reads as a dead store.
    allowed = set(getattr(settings, 'ALLOWED_HOSTS', []) or [])
    if host not in allowed and '*' not in allowed:
        host = next((h for h in allowed if h and not h.startswith('.')), 'testserver')

    client = Client()
    pages: list[PageFacts] = []
    partial = False
    probe = NotFoundFacts(path='', status=0)
    # Every sitemap path, even under a limit: an orphan can only be named when
    # the crawl read the whole sitemap.
    all_paths = _paths(None)
    paths = all_paths[:limit] if limit else all_paths
    try:
        probe = _probe_missing(client, host)
        for path in paths:
            pages.append(_facts(client, path, host))
    except SoftTimeLimitExceeded:
        # Report what was checked rather than lose the whole night's work.
        partial = True
        logger.warning('site_audit: time budget spent after %d pages', len(pages))
    crawled = time.monotonic()
    untranslated: dict[str, list[str]] = {}
    if not partial:
        try:
            untranslated = _untranslated(client, host, pages)
        except SoftTimeLimitExceeded:
            partial = True

    extra = _Extra(client=Client(), host=host, deadline=started + EXTRA_DEADLINE_S)
    extra_findings: list[Finding] = []
    measured = {'crawl_s': round(crawled - started, 1)}
    if partial:
        # Past the soft limit the hard kill follows in two minutes: store what
        # the crawl found, start nothing new.
        extra.note('orphans', 'the scan stopped early at the time limit')
    else:
        try:
            phase = time.monotonic()
            extra_findings += _claim_findings(extra, pages)
            measured['claims_s'] = round(time.monotonic() - phase, 1)
            phase = time.monotonic()
            link_sources = _link_sources(extra, pages)
            measured['pagination_s'] = round(time.monotonic() - phase, 1)
            phase = time.monotonic()
            extra_findings += _link_findings(extra, pages, link_sources)
            measured['links_s'] = round(time.monotonic() - phase, 1)
            if limit and len(paths) < len(all_paths):
                extra.note(
                    'orphans', f'the scan read {len(paths)} of {len(all_paths)} sitemap URLs'
                )
            extra_findings += _orphan_findings(extra, pages, link_sources)
        except SoftTimeLimitExceeded:
            partial = True
            extra.note('orphans', 'the scan stopped early at the time limit')
    for page in pages:
        page.links = []  # read; the cached report never carries them
    findings = _not_found_findings(probe) + _analyse(pages, untranslated) + extra_findings
    findings.sort(key=lambda f: (_ORDER.get(f.severity, 9), -f.count))
    score = max(0, 100 - sum(_PENALTY.get(f.severity, 0) for f in findings))
    measured['total_s'] = round(time.monotonic() - started, 1)
    return {
        'generated_at': timezone.now().isoformat(),
        'pages_checked': len(pages),
        'partial': partial,
        'score': score,
        'findings': [f.as_dict() for f in findings],
        'coverage': _coverage(pages),
        'not_found_probe': {'path': probe.path, 'status': probe.status},
        'checks': extra.summary(),
        'measured': measured,
    }


# ── What the markup claims, against the page and the claim's owner ───────────


class _Extra:
    """The fetches and counts of the checks that run after the sitemap crawl.

    Its own client, so a link that sets something in the session (a currency
    switch) cannot change what the crawl rendered; every fetch is cached for the
    run, capped, and stops at the deadline.
    """

    def __init__(self, *, client, host: str, deadline: float):
        self.client = client
        self.host = host
        self.hosts = _own_hosts(host)
        self.deadline = deadline
        self.counts = {
            'products': 0,
            'products_without_owner': 0,
            'images': 0,  # distinct images checked
            'image_fetches': 0,  # requests, a redirect's hops included
            'images_off_host': 0,
            'link_targets': 0,
            'link_fetches': 0,
            'pagination_fetches': 0,
        }
        self.capped: dict[str, bool] = {}
        self.notes: dict[str, str] = {}
        self.finals: dict[str, str] = {}  # link target → where its redirects end
        self._responses: dict[str, tuple[int, str, str]] = {}

    def note(self, check: str, reason: str) -> None:
        self.notes.setdefault(check, reason)

    def fetch(self, path: str, *, counter: str, cap: int) -> tuple[int, str, str]:
        """(status, Location, Content-Type) for one same-host path, cached."""
        if path in self._responses:
            return self._responses[path]
        if self.counts[counter] >= cap or time.monotonic() > self.deadline:
            self.capped[counter] = True
            raise _Capped(counter)
        self.counts[counter] += 1
        try:
            response = _get(self.client, path, self.host)
        except SoftTimeLimitExceeded:
            raise
        except Exception as e:  # noqa: BLE001 — one bad fetch must not end the audit
            logger.warning('site_audit: %s raised %s', path, e)
            self._responses[path] = (0, '', '')
            return self._responses[path]
        result = (
            response.status_code,
            response.get('Location', '') or '',
            response.get('Content-Type', '') or '',
        )
        response.close()
        self._responses[path] = result
        return result

    def local(self, url: str) -> str:
        """The site-relative path of a URL on this store, or '' for another host
        (or for one that does not parse, which nothing could fetch)."""
        try:
            parts = urlsplit(url or '')
        except ValueError:
            return ''
        if parts.netloc and parts.netloc not in self.hosts:
            return ''
        if parts.scheme and parts.scheme not in ('http', 'https'):
            return ''
        return (parts.path or '/') + (f'?{parts.query}' if parts.query else '')

    def summary(self) -> dict:
        orphans = self.notes.get('orphans', '')
        return {
            **self.counts,
            'capped': sorted(k for k, v in self.capped.items() if v),
            'orphans_checked': not orphans,
            'orphans_skipped_because': orphans,
        }


def _owner(claim: dict, page_path: str, owners: dict):
    """(product, variant) a claim speaks for, or (None, None).

    By SKU first; a page's own product also by its slug, from `/products/<slug>/`,
    or from another page's last path segment when the product's name matches too
    (a booking listing's product shares its slug and name). Nothing else: a
    wrong owner would turn a correct claim into a finding.
    """
    from plugins.installed.catalog.models import Product, ProductVariant

    key = (claim['sku'], claim['url'] or page_path, claim['name'], claim['main'])
    if key in owners:
        return owners[key]
    product = variant = None
    if claim['sku']:
        if not claim['main']:
            variant = (
                ProductVariant.objects.filter(sku=claim['sku']).select_related('product').first()
            )
            product = variant.product if variant else None
        else:
            product = Product.objects.filter(sku=claim['sku']).first()
    if product is None and claim['main']:
        try:
            claimed = urlsplit(claim['url']).path
        except ValueError:
            claimed = ''
        path = _strip_language(claimed or page_path)
        segments = [s for s in path.split('/') if s]
        if segments:
            candidate = Product.objects.filter(slug=unquote(segments[-1])).first()
            if candidate is not None and (
                path.startswith('/products/') or candidate.name == claim['name']
            ):
                product = candidate
    owners[key] = (product, variant)
    return owners[key]


def _owner_price(product, variant):
    """The price the store shows and charges now, through the one pricing seam."""
    from core.pricing import apply_price_filter
    from plugins.installed.catalog.models import cheapest_variant_price

    if variant is not None:
        base = variant.effective_price
    elif product.product_type == 'variable':
        base = cheapest_variant_price(v for v in product.variants.all() if v.is_active)
        base = base if base is not None else product.price
    else:
        base = product.price
    return apply_price_filter(base, product=product) if base is not None else None


def _schema_token(value: str) -> str:
    return str(value or '').rstrip('/').rsplit('/', 1)[-1].lower()


def _price_mismatch(claim: dict, product, variant, currency: str) -> str:
    """'claims X; the price is Y' when the offer's price is not the store's, else ''."""
    owner = _owner_price(product, variant)
    if owner is None:
        return ''
    same_amount = Decimal(claim['price']) == owner.amount.quantize(Decimal('0.01'))
    same_currency = not claim['currency'] or claim['currency'] == str(owner.currency)
    if same_amount and same_currency:
        return ''
    where = f' (the store sells in {currency})' if str(owner.currency) != currency else ''
    claimed = f'{claim["price"]} {claim["currency"]}'.strip()
    return (
        f'{claim["name"] or claim["sku"]} claims {claimed}; '
        f'the price is {owner.amount:.2f} {owner.currency}{where}'
    )


def _stock_mismatch(claim: dict, product) -> str:
    """'claims X; inventory says Y' for a page's own product, else ''.

    Not for a service: a booking's availability is its sessions, which the
    booking app answers, not inventory.
    """
    from plugins.feed_mapping import availability_to_schema

    if not claim['main'] or not claim['availability'] or product.product_type == 'service':
        return ''
    owner = _schema_token(availability_to_schema(product))
    claimed = _schema_token(claim['availability'])
    return '' if claimed == owner else f'claims {claimed}; inventory says {owner}'


def _claim_findings(extra: _Extra, pages: list[PageFacts]) -> list[Finding]:
    """Prices, availability and images the markup claims, against their owners."""
    from plugins.dropshipping.importer import store_currency
    from plugins.installed.seo.services.images import image_size

    stale, wrong_stock, broken, sizes = [], [], [], []
    owners: dict = {}
    images: dict[str, str] = {}  # url → '' when fine, else what came back
    currency = store_currency()
    for page in (p for p in pages if p.status == 200):
        for claim in page.claims:
            extra.counts['products'] += 1
            product, variant = _owner(claim, page.path, owners)
            if product is None:
                extra.counts['products_without_owner'] += 1
                continue
            if claim['price'] and (found := _price_mismatch(claim, product, variant, currency)):
                stale.append(f'{page.path}: {found}')
            if found := _stock_mismatch(claim, product):
                wrong_stock.append(f'{page.path}: {found}')
        named = [u for c in page.claims for u in c['images']]
        if page.og_image:
            named.append(page.og_image)
        for url in dict.fromkeys(named):
            problem = _image_problem(extra, url, images)
            if problem:
                broken.append(f'{page.path}: {url} {problem}')
        if page.og_image and page.og_size and extra.local(page.og_image):
            measured = image_size(page.og_image)
            if measured and tuple(measured) != tuple(page.og_size):
                sizes.append(
                    f'{page.path}: declares {page.og_size[0]}×{page.og_size[1]}, '
                    f'the file is {measured[0]}×{measured[1]}'
                )
    return [
        f
        for f in (
            _finding(
                'markup_price_stale',
                CRITICAL,
                'Structured data states a price the store no longer charges',
                "The offer in the page's markup names a different price than the store "
                'charges today. Google shows that price in results and Merchant Center '
                'treats a mismatch as a policy violation; usually a cached page or a copy of '
                'the price that missed an edit.',
                stale,
                'Products',
                '/dashboard/products/',
            ),
            _finding(
                'markup_availability_wrong',
                CRITICAL,
                'Structured data states stock the store does not have',
                'The offer says in stock (or out of stock) while inventory says otherwise. '
                'A shopper who clicks a result for an item that cannot be bought leaves, and '
                'Merchant Center disapproves the listing.',
                wrong_stock,
                'Stock',
                '/dashboard/products/',
            ),
            _finding(
                'markup_image_broken',
                CRITICAL,
                'Structured data or og:image names an image that does not load',
                'Google drops a product result whose image fails, and a shared link shows '
                'an empty card.',
                broken,
            ),
            _finding(
                'og_image_size_wrong',
                WARNING,
                'og:image declares a size its file does not have',
                'A share card is laid out from the declared size; the wrong one crops or '
                'stretches the picture.',
                sizes,
            ),
        )
        if f
    ]


def _image_problem(extra: _Extra, url: str, seen: dict[str, str]) -> str:
    """'' when the image answers 200 with an image, else what came back.

    Another host's image (a CDN, Wikimedia) is counted and skipped: its answer
    is not this store's to fix, and the audit sends no request off the host.
    """
    if url in seen:
        return seen[url]
    path = extra.local(url)
    if not path:
        extra.counts['images_off_host'] += 1
        seen[url] = ''
        return ''
    extra.counts['images'] += 1
    try:
        status, location, kind = extra.fetch(path, counter='image_fetches', cap=MAX_IMAGE_FETCHES)
        for _ in range(MAX_HOPS):
            nxt = extra.local(urljoin(f'https://{extra.host}{path}', location)) if location else ''
            if not (300 <= status < 400) or not nxt:
                break
            path = nxt
            status, location, kind = extra.fetch(
                path, counter='image_fetches', cap=MAX_IMAGE_FETCHES
            )
    except _Capped:
        seen[url] = ''
        return ''
    ok = status == 200 and kind.split(';', 1)[0].strip().lower().startswith('image/')
    if not ok and _ships_static_file(url):
        # A theme's own file (the travel themes' og-default.jpg) may be served by
        # whatever stands in front of the app (WhiteNoise here, nginx or a CDN
        # elsewhere, nothing at all under the test runner), so an in-process 404
        # proves nothing about it; the file being in the build does.
        ok = True
    seen[url] = '' if ok else f'answers {status or "nothing"} {kind.split(";", 1)[0]}'.strip()
    return seen[url]


def _ships_static_file(url: str) -> bool:
    """Whether a /static/ URL names a file the store's build holds."""
    from django.conf import settings

    from plugins.installed.seo.services.images import _local_image_path

    static_url = str(getattr(settings, 'STATIC_URL', '/static/') or '/static/')
    return urlsplit(str(url or '')).path.startswith(static_url) and bool(_local_image_path(url))


# ── Links between pages: redirects, chains, orphans ──────────────────────────


def _link_sources(extra: _Extra, pages: list[PageFacts]) -> dict[str, list[str]]:
    """{link target: [pages linking to it]}, the sitemap pages' links plus those of
    the listing pages they paginate to (`rel=next`): a product only on page 7 of
    a category is linked from page 7, and is not an orphan."""
    sources: dict[str, list[str]] = {}

    def add(page: PageFacts, label: str) -> None:
        for target in page.links:
            sources.setdefault(target, []).append(label)

    queue = [p.next_href for p in pages if p.status == 200 and p.next_href]
    for page in pages:
        add(page, page.path)
    seen: set[str] = set()
    while queue:
        nxt = queue.pop(0)
        if nxt in seen:
            continue
        seen.add(nxt)
        if (
            extra.counts['pagination_fetches'] >= MAX_PAGINATION_FETCHES
            or time.monotonic() > extra.deadline
        ):
            extra.capped['pagination_fetches'] = True
            extra.note('orphans', 'not every listing page past the first was read')
            break
        extra.counts['pagination_fetches'] += 1
        page = _facts(extra.client, nxt, extra.host)
        add(page, nxt)
        if page.status == 200 and page.next_href:
            queue.append(page.next_href)
    extra.counts['link_targets'] = len(sources)
    return sources


def _hops(extra: _Extra, start: str, known: dict[str, tuple[int, str]]) -> list[str]:
    """Where a redirect from ``start`` leads, hop by hop ([] when it is not one).

    At most MAX_HOPS, never fetched off the host: an off-host target ends the
    chain as a full URL. A sitemap page's answer comes from the crawl.
    """
    out: list[str] = []
    current, visited = start, {start}
    for _ in range(MAX_HOPS):
        if current in known:
            status, location = known[current]
        else:
            status, location, _kind = extra.fetch(
                current, counter='link_fetches', cap=MAX_LINK_FETCHES
            )
        if not (300 <= status < 400) or not location:
            break
        absolute = urljoin(f'https://{extra.host}{current}', location)
        nxt = extra.local(absolute)
        out.append(nxt or absolute)
        if not nxt or nxt in visited:
            break
        visited.add(nxt)
        current = nxt
    return out


def _link_findings(
    extra: _Extra, pages: list[PageFacts], sources: dict[str, list[str]]
) -> list[Finding]:
    known = {p.path: (p.status, p.redirect_to) for p in pages}
    one_hop, chains = [], []
    try:
        for target in sorted(sources):
            hops = _hops(extra, target, known)
            if not hops:
                continue
            extra.finals[target] = hops[-1]
            if any(h.startswith('/') and _skipped_path(h) for h in hops):
                # A page that needs an account sends a visitor to sign in (the
                # affiliate and vendor sign-ups do): that is the door, not a
                # detour, and linking to the sign-in page instead would lose the
                # page they came for.
                continue
            for source in sorted(set(sources[target])):
                if len(hops) == 1:
                    one_hop.append(f'{source} links to {target} → {hops[0]}')
                else:
                    chains.append(
                        f'{source} links to {target} → {" → ".join(hops)} ({len(hops)} hops)'
                    )
        for page in pages:
            if 300 <= page.status < 400:
                hops = _hops(extra, page.path, known)
                if len(hops) > 1:
                    chains.append(f'sitemap: {page.path} → {" → ".join(hops)} ({len(hops)} hops)')
    except _Capped:
        extra.note('orphans', 'not every redirect a link leads to was followed')
    return [
        f
        for f in (
            _finding(
                'redirect_chain',
                CRITICAL,
                'Links and sitemap URLs that redirect more than once',
                'Each hop costs a crawler a request and a visitor a round trip, and Google '
                'stops following after a few. Point the first URL straight at the last.',
                chains,
                'Review redirects',
                '/dashboard/seo/redirects/',
            ),
            _finding(
                'link_to_redirect',
                WARNING,
                'Pages link to a URL that redirects',
                'The link works, but every click and every crawl takes a detour. Link to '
                'the page the redirect leads to.',
                one_hop,
                'Review redirects',
                '/dashboard/seo/redirects/',
            ),
        )
        if f
    ]


def _orphan_findings(
    extra: _Extra, pages: list[PageFacts], sources: dict[str, list[str]]
) -> list[Finding]:
    """Sitemap pages no other page links to, named only after a whole-sitemap crawl."""
    if extra.notes.get('orphans'):
        return []
    linked: set[str] = set()
    for target, from_pages in sources.items():
        if any(source != target for source in from_pages):
            linked.add(unquote(target))
            final = extra.finals.get(target, '')
            if final.startswith('/'):
                linked.add(unquote(final.split('?', 1)[0]))
    orphans = [
        p.path
        for p in pages
        if p.status == 200
        and p.path != '/'
        and 'noindex' not in p.robots.lower()
        and unquote(p.path) not in linked
    ]
    found = _finding(
        'orphan_page',
        NOTICE,
        'Sitemap pages no other page links to',
        'A page only the sitemap knows about gets little weight from search engines and '
        'no visitors from the rest of the shop. Link it from a category, a menu or a '
        'related page.',
        orphans,
    )
    return [found] if found else []


def _finding(code, severity, title, why, matches, fix_label='', fix_url='') -> Finding | None:
    if not matches:
        return None
    return Finding(
        code=code,
        severity=severity,
        title=title,
        why=why,
        count=len(matches),
        examples=sorted(matches)[:MAX_EXAMPLES],
        fix_label=fix_label,
        fix_url=fix_url,
    )


def _untranslated(client, host: str, pages: list[PageFacts]) -> dict[str, list[str]]:
    """`{language: [path]}`: the pages whose copy in that language is not translated yet.

    A page about an object nobody translated declares no alternates on purpose, and
    its `/sr/` copy names the default-language page as its canonical (core.i18n,
    `seo.head.builder`). That canonical is how a crawler that sees only HTML can
    tell "not translated yet" from "alternates missing": only pages without
    hreflang are fetched again, one request per other language.
    """
    from django.conf import settings
    from django.urls import translate_url
    from django.utils import translation

    codes = [c.lower() for c, _ in (getattr(settings, 'LANGUAGES', None) or [])]
    default = (settings.LANGUAGE_CODE or '').lower()
    others = [c for c in codes if c != default and c != default.split('-')[0]]
    out: dict[str, list[str]] = {}
    for page in pages:
        if page.status != 200 or page.hreflangs or not page.canonical:
            continue
        if (urlsplit(page.canonical).path or '/') != page.path:
            continue
        for code in others:
            with translation.override(settings.LANGUAGE_CODE):
                copy_path = translate_url(page.path, code)
            if copy_path == page.path:
                continue  # a route with no copy in that language
            with translation.override(settings.LANGUAGE_CODE):
                copy = _facts(client, copy_path, host)
            if copy.status == 200 and (urlsplit(copy.canonical).path or '/') == page.path:
                out.setdefault(code, []).append(page.path)
    return out


def _analyse(  # noqa: PLR0912 — a linear check list
    pages: list[PageFacts], untranslated: dict[str, list[str]] | None = None
) -> list[Finding]:
    """Turn page facts into findings, most severe first."""
    from django.conf import settings

    from core.i18n.services import language_name

    ok = [p for p in pages if p.status == 200]
    untranslated = untranslated or {}
    not_yet = {path for paths in untranslated.values() for path in paths}
    out: list[Finding] = []

    def add(code, severity, title, why, matches, fix_label='', fix_url=''):
        found = _finding(code, severity, title, why, matches, fix_label, fix_url)
        if found:
            out.append(found)

    add(
        'markup_price_not_on_page',
        CRITICAL,
        'Structured data states a price the page does not show',
        "Google requires an offer's price to be the one a visitor sees on the page; a "
        'price only the markup carries is a structured-data spam signal and can cost '
        'the product its rich result.',
        [
            f'{p.path}: {c["name"] or c["sku"]} claims {c["price"]} {c["currency"]}; '
            'the page shows no such price'
            for p in ok
            for c in p.claims
            if c.get('main') and c.get('shown') is False
        ],
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
    from urllib.parse import urlsplit

    add(
        'sitemap_canonical_elsewhere',
        CRITICAL,
        'Sitemap lists pages whose canonical is another URL',
        'The sitemap says "index this page" and the page says "index that one '
        'instead". Google drops one claim — usually the sitemap entry — and trusts '
        'the rest of the sitemap less.',
        [
            f'{p.path} → {p.canonical}'
            for p in ok
            if p.canonical and (urlsplit(p.canonical).path or '/') != (urlsplit(p.path).path or '/')
        ],
        'Review index rules',
        '/dashboard/seo/rules/',
    )
    add(
        'hreflang_not_canonical',
        WARNING,
        'hreflang alternates that are not canonical URLs',
        'An alternate must name the canonical URL of each language version. One that '
        'carries a tracking or filter parameter the canonical drops is ignored, and the '
        'language versions stop being connected.',
        [
            p.path
            for p in ok
            if any(
                urlsplit(href).query and urlsplit(href).query != urlsplit(p.canonical or '').query
                for _code, href in p.hreflang_hrefs
            )
        ],
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
            [p.path for p in ok if not p.hreflangs and p.path not in not_yet],
        )
        for code, paths in sorted(untranslated.items()):
            add(
                f'not_translated_{code}',
                INFO,
                f'Not yet translated into {language_name(code)}',
                f'These pages are shown in the default language on the {language_name(code)} '
                'side of the store, so they name the default-language page as theirs and '
                'claim no other language. Once their text is translated and reviewed, each '
                'gets its own page in that language.',
                paths,
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

    out.sort(key=lambda f: (_ORDER.get(f.severity, 9), -f.count))
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
    from django.utils import timezone

    try:
        cache.set(RUNNING_KEY, timezone.now().isoformat(), _RUNNING_TTL)
    except Exception:  # noqa: BLE001 — the marker only stops a second run
        logger.debug('site_audit: could not mark the run', exc_info=True)
    try:
        report = collect(limit=limit)
    finally:
        try:
            cache.delete(RUNNING_KEY)
        except Exception:  # noqa: BLE001
            logger.debug('site_audit: could not clear the run marker', exc_info=True)
    try:
        cache.set(CACHE_KEY, report, CACHE_TTL)
    except Exception:  # noqa: BLE001
        logger.warning('site_audit: could not cache the report', exc_info=True)
    return report


class AuditRefused(Exception):
    """A scan was not queued; the message says why, in the merchant's words."""

    def __init__(self, message: str, *, busy: bool = True):
        super().__init__(message)
        self.busy = busy


def _minutes_since(stamp) -> float | None:
    from datetime import datetime

    from django.utils import timezone

    try:
        when = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
    if timezone.is_naive(when):
        when = timezone.make_aware(when)
    return (timezone.now() - when).total_seconds() / 60


def queue_site_audit() -> str:
    """Queue `seo.site_audit` once, for the dashboard's button and Linda's tool.

    Refused while a scan is running, and for ten minutes after one finished or
    was queued: a scan renders every page of the shop, and asking twice buys the
    same report at twice the load.
    """
    from django.utils import timezone

    try:
        running = cache.get(RUNNING_KEY)
    except Exception:  # noqa: BLE001
        running = None
    if running:
        raise AuditRefused(
            f'A site scan is already running (started {str(running)[11:16]} UTC). '
            'Its findings replace these when it finishes.'
        )
    last = cached() or {}
    age = _minutes_since(last.get('generated_at'))
    if age is not None and age * 60 < RERUN_AFTER_S:
        wait = max(1, int(RERUN_AFTER_S / 60 - age + 0.999))
        raise AuditRefused(
            f'The last scan finished {int(age)} minute(s) ago; a new one can start in '
            f'{wait} minute(s).'
        )
    now = timezone.now().isoformat()
    try:
        claimed = cache.add(QUEUED_KEY, now, RERUN_AFTER_S)
    except Exception:  # noqa: BLE001 — no cache: one more scan is the worst case
        claimed = True
    if not claimed:
        raise AuditRefused(
            'A site scan was queued less than ten minutes ago and has not finished yet.'
        )
    try:
        from plugins.installed.seo.tasks import site_audit_task

        site_audit_task.delay()
    except Exception as e:
        cache.delete(QUEUED_KEY)
        logger.warning('seo: could not queue the site audit: %s', e, exc_info=True)
        raise AuditRefused(
            'Could not queue the site audit — no background worker is reachable. '
            'Run `manage.py seo_site_audit` on the server instead.',
            busy=False,
        ) from e
    return now
