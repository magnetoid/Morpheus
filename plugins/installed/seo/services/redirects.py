"""Redirect resolution + 404 monitor + auto-suggester.

``resolve_redirect`` runs on **every** storefront request from the middleware,
so the cost of a miss is the number that matters: the whole active ruleset is
compiled once into a small cached structure and consulted in memory, rather
than asking the database on each request as the first version did.

Three match types, and their precedence is load-bearing:

  1. ``exact``  — the full path, and it always wins.
  2. ``prefix`` — longest prefix first.
  3. ``regex``  — last, in creation order.

Without that ordering a broad ``/books/`` prefix rule silently swallows the
specific ``/books/dune/`` rule the merchant added afterwards, and nothing about
the symptom points at the cause.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from ._helpers import logger

# One cache entry holds the compiled ruleset. Bumping the suffix is how a
# structural change to that payload invalidates every worker's copy at once —
# Redis survives a deploy (it is not recreated), so a stale shape would
# otherwise be served by the new code.
_RULES_CACHE_KEY = 'seo:redirect_rules:v1'
_RULES_CACHE_TTL = 300

# Above this many exact rules the compiled map stops being a sensible thing to
# hold in the cache (and to ship to every worker), so exact matching falls back
# to a single indexed query per request. Prefix/regex rules stay compiled —
# there are never many of them, and they cannot be looked up by equality.
_MAX_CACHED_EXACT = 5000

_CHAIN_MAX_DEPTH = 10


def normalise_path(path: str) -> str:
    """A comparable form of a path: no host, no query, no fragment, leading slash.

    Redirect rows are matched against ``request.path_info``, so anything a
    merchant pastes in — a full URL, a bare slug, a path with ``?utm_source`` —
    has to be reduced to the same shape or the rule simply never fires.
    """
    value = (path or '').strip()
    if not value:
        return ''
    if '://' in value:
        parts = urlsplit(value)
        value = parts.path or '/'
    else:
        value = value.split('#', 1)[0].split('?', 1)[0]
    if not value.startswith('/'):
        value = '/' + value
    return value[:500]


def normalise_target(target: str) -> str:
    """A redirect target may legitimately be an absolute URL (an off-site move)
    or carry a query string, so only the obviously-wrong shapes are corrected."""
    value = (target or '').strip()
    if not value:
        return ''
    if '://' in value or value.startswith('//'):
        return value[:500]
    if not value.startswith('/'):
        value = '/' + value
    return value[:500]


# -- the compiled ruleset -------------------------------------------------
def _compile_rules() -> dict:
    from plugins.installed.seo.models import Redirect

    rows = Redirect.objects.filter(is_active=True).values_list(
        'from_path', 'to_path', 'status_code', 'match_type'
    )
    exact: dict[str, tuple[str, int]] = {}
    prefix: list[tuple[str, str, int]] = []
    regex: list[tuple[str, str, int]] = []
    exact_count = 0
    for from_path, to_path, status, match_type in rows:
        if match_type == Redirect.MATCH_PREFIX:
            prefix.append((from_path, to_path, status))
        elif match_type == Redirect.MATCH_REGEX:
            regex.append((from_path, to_path, status))
        else:
            exact_count += 1
            if exact_count <= _MAX_CACHED_EXACT:
                exact[from_path] = (to_path, status)
    # Longest prefix wins, so a rule for /books/fiction/ beats one for /books/.
    prefix.sort(key=lambda r: len(r[0]), reverse=True)
    return {
        'exact': exact,
        'prefix': prefix,
        'regex': regex,
        # True when the exact map is complete; False means fall back to a query.
        'exact_complete': exact_count <= _MAX_CACHED_EXACT,
    }


def _rules() -> dict:
    from django.core.cache import cache

    try:
        cached = cache.get(_RULES_CACHE_KEY)
        if cached is not None:
            return cached
    except Exception:  # noqa: BLE001 — a broken cache must not break the site
        return _compile_rules()
    rules = _compile_rules()
    try:
        cache.set(_RULES_CACHE_KEY, rules, _RULES_CACHE_TTL)
    except Exception:  # noqa: BLE001
        logger.debug('seo: could not cache redirect rules', exc_info=True)
    return rules


def invalidate_redirect_cache() -> None:
    """Drop the compiled ruleset. Called whenever a Redirect row changes.

    Without this a merchant's new redirect appears to do nothing for up to the
    cache TTL — the exact failure mode that makes people distrust the feature.
    """
    from django.core.cache import cache

    try:
        cache.delete(_RULES_CACHE_KEY)
    except Exception:  # noqa: BLE001
        logger.debug('seo: redirect cache invalidation failed', exc_info=True)


def _match(path: str, rules: dict) -> tuple[str, int] | None:
    hit = rules['exact'].get(path)
    if hit is not None:
        return hit
    if not rules.get('exact_complete', True):
        from django.db import DatabaseError

        from plugins.installed.seo.models import Redirect

        try:
            row = (
                Redirect.objects.filter(
                    from_path=path, match_type=Redirect.MATCH_EXACT, is_active=True
                )
                .values_list('to_path', 'status_code')
                .first()
            )
        except DatabaseError as e:
            logger.warning('seo: redirect lookup db error: %s', e)
            row = None
        if row:
            return row[0], row[1]

    for from_path, to_path, status in rules['prefix']:
        if path.startswith(from_path):
            # A prefix rule moves a whole branch: /old-shop/x/ → /shop/x/.
            # Substituting only the matched head is what makes that work; a
            # rule that wants a single destination should be an exact rule.
            remainder = path[len(from_path) :]
            return (to_path.rstrip('/') + '/' + remainder.lstrip('/') if remainder else to_path), (
                status
            )

    for pattern, to_path, status in rules['regex']:
        try:
            m = re.match(pattern, path)
        except re.error:
            # A merchant can type an invalid pattern; it must cost that one rule,
            # not every request on the site.
            logger.warning('seo: skipping invalid redirect regex %r', pattern)
            continue
        if m:
            try:
                return (m.expand(to_path) if '\\' in to_path else to_path), status
            except re.error:
                return to_path, status
    return None


def resolve_redirect(path: str) -> tuple[str, int] | None:
    """``(target_path, status_code)`` for ``path``, or None.

    A 410 rule returns ``('', 410)`` — there is no target; the middleware
    turns that into a Gone response.
    """
    path = normalise_path(path)
    if not path:
        return None
    try:
        rules = _rules()
    except Exception as e:  # noqa: BLE001 — an unmigrated DB during a deploy
        logger.debug('seo: redirect rules unavailable: %s', e)
        return None
    hit = _match(path, rules)
    if hit is None:
        return None
    to_path, status = hit
    if status == 410:
        return '', 410
    return to_path, status


def record_redirect_hit(path: str) -> None:
    """Best-effort hit counter. Never on the critical path of the response."""
    from django.db import DatabaseError
    from django.db.models import F
    from django.utils import timezone

    from plugins.installed.seo.models import Redirect

    try:
        Redirect.objects.filter(from_path=normalise_path(path), is_active=True).update(
            hit_count=F('hit_count') + 1, last_hit_at=timezone.now()
        )
    except DatabaseError:
        logger.debug('seo: redirect hit counter failed', exc_info=True)


# -- writing rules --------------------------------------------------------
def collapse_chain(from_path: str, to_path: str) -> str:
    """Follow ``to_path`` through existing exact rules to its final destination.

    Redirect chains cost crawl budget and lose a little authority at every hop,
    and they accumulate on their own: rename a product twice and A→B→C exists
    without anyone deciding it should. Collapsing on write keeps every rule one
    hop. Returns the original target if following it would loop.
    """
    from plugins.installed.seo.models import Redirect

    seen = {from_path}
    current = to_path
    for _ in range(_CHAIN_MAX_DEPTH):
        if current in seen:
            return to_path  # a cycle — leave the merchant's value alone
        seen.add(current)
        try:
            nxt = (
                Redirect.objects.filter(
                    from_path=current, match_type=Redirect.MATCH_EXACT, is_active=True
                )
                .exclude(status_code=410)
                .values_list('to_path', flat=True)
                .first()
            )
        except Exception:  # noqa: BLE001
            return current
        if not nxt or nxt == current:
            return current
        current = nxt
    return current


def validate_redirect(
    *, from_path: str, to_path: str, status_code: int, match_type: str = 'exact'
) -> list[str]:
    """Merchant-facing checks. Returns a list of human-readable problems.

    Deliberately *not* in ``Redirect.save()``: these are policy, and an
    automated path (slug history, CSV import) needs to report them rather than
    raise mid-save. Loop and self-reference checks are structural and live here
    too, because a self-redirect is an infinite loop the browser shows the
    visitor, not a subtle SEO issue.
    """
    problems: list[str] = []
    # A regex rule's `from_path` is a PATTERN, and normalising it would prepend a
    # slash to `^/old/(.*)$` — leaving a pattern that compiles but never matches,
    # and a self-redirect check comparing something the merchant never typed.
    is_regex = match_type == 'regex'
    src = (from_path or '').strip() if is_regex else normalise_path(from_path)
    dst = normalise_target(to_path)
    if not src:
        problems.append('The path to redirect from is required.')
    if status_code == 410:
        return problems  # a 410 has no target to check
    if not dst:
        problems.append('A destination is required (or use 410 for a removed page).')
    if src and dst and src == dst:
        problems.append('That redirects the path to itself.')
    if is_regex and src:
        try:
            re.compile(src)
        except re.error as e:
            problems.append(f'Not a valid regular expression: {e}')
    if dst == '/' and _blocks_homepage_redirects():
        problems.append(
            'Redirecting to the homepage reads as a soft 404 and loses the page '
            'rather than moving it. Point it at the closest live page, use 410 if '
            'it is really gone, or turn this guard off in SEO settings.'
        )
    return problems


def _blocks_homepage_redirects() -> bool:
    from ._helpers import site_settings

    try:
        return bool(getattr(site_settings(), 'block_homepage_redirects', True))
    except Exception:  # noqa: BLE001
        return True


# -- CSV import / export --------------------------------------------------
CSV_COLUMNS = ('from_path', 'to_path', 'status_code', 'match_type', 'note')


def export_redirects_csv() -> str:
    import csv
    import io

    from plugins.installed.seo.models import Redirect

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for row in Redirect.objects.all().order_by('from_path'):
        writer.writerow([row.from_path, row.to_path, row.status_code, row.match_type, row.note])
    return buf.getvalue()


def import_redirects_csv(text: str) -> dict:
    """Upsert rules from CSV. Returns {created, updated, skipped, errors}.

    Rows are validated individually and a bad one is reported rather than
    aborting the import — a 500-row migration from another platform always has
    a few malformed lines, and losing the other 495 helps nobody.
    """
    import csv
    import io

    from plugins.installed.seo.models import Redirect

    result = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}
    reader = csv.DictReader(io.StringIO(text))
    for line_no, raw in enumerate(reader, start=2):
        src = normalise_path(raw.get('from_path') or raw.get('from') or '')
        dst = normalise_target(raw.get('to_path') or raw.get('to') or '')
        match_type = (raw.get('match_type') or 'exact').strip().lower()
        if match_type not in {c[0] for c in Redirect.MATCH_CHOICES}:
            match_type = 'exact'
        try:
            status = int(raw.get('status_code') or 301)
        except (TypeError, ValueError):
            status = 301
        if status not in {c[0] for c in Redirect.KIND_CHOICES}:
            status = 301
        problems = validate_redirect(
            from_path=src, to_path=dst, status_code=status, match_type=match_type
        )
        if problems:
            result['skipped'] += 1
            result['errors'].append(f'Line {line_no}: {problems[0]}')
            continue
        _, created = Redirect.objects.update_or_create(
            from_path=src,
            match_type=match_type,
            defaults={
                'to_path': dst,
                'status_code': status,
                'note': (raw.get('note') or '')[:200],
                'source': 'import',
                'is_active': True,
            },
        )
        result['created' if created else 'updated'] += 1
    invalidate_redirect_cache()
    return result


# -- 404 monitor ----------------------------------------------------------
def record_404(*, path: str, referrer: str = '') -> None:
    from django.db.models import F as _F
    from django.utils import timezone

    from plugins.installed.seo.models import NotFoundLog

    if not path or len(path) > 500:
        return
    try:
        existing = NotFoundLog.objects.filter(path=path).first()
        if existing:
            # `last_seen_at` is auto_now, which a queryset .update() does NOT
            # trigger — so a repeatedly-hit 404 kept its first-sighting
            # timestamp forever and every "recent 404s" view was reading a lie.
            NotFoundLog.objects.filter(pk=existing.pk).update(
                hit_count=_F('hit_count') + 1, last_seen_at=timezone.now()
            )
        else:
            NotFoundLog.objects.create(path=path, referrer=referrer[:500])
    except Exception:  # noqa: BLE001, S110
        pass


def suggest_redirect(path: str) -> str:  # noqa: PLR0911, PLR0912
    """Suggest a live URL for a 404 path.

    Strategy:
      1. The path's own history — if this exact URL used to belong to an object
         that still exists, that is not a guess, it is the answer.
      2. Extract the most-significant slug segment (the last non-empty path
         component without a file extension).
      3. Fuzzy-match it against the live product slug index using
         ``difflib.get_close_matches``. This catches typos and renamings
         (e.g. ``the-greate-gatsby`` → ``the-great-gatsby``).
      4. Fall back to token-overlap against category slugs.
      5. Last resort: the legacy substring lookup we used to do.
    """
    if not path:
        return ''
    known = _path_from_history(path)
    if known:
        return known
    try:
        from plugins.installed.catalog.models import Category, Product
    except Exception:  # noqa: BLE001
        return ''

    import difflib

    segments = [s for s in path.strip('/').split('/') if s]
    if not segments:
        return ''
    target_slug = re.sub(r'\.[a-z0-9]{1,5}$', '', segments[-1].lower())
    target_slug = re.sub(r'[^a-z0-9-]', '', target_slug)
    tokens = [t for t in target_slug.split('-') if t]
    if not target_slug:
        return ''

    try:
        product_slugs = list(Product.objects.filter(status='active').values_list('slug', flat=True))
    except Exception:  # noqa: BLE001
        product_slugs = []

    if product_slugs and target_slug:
        close = difflib.get_close_matches(target_slug, product_slugs, n=1, cutoff=0.6)
        if close:
            return f'/products/{close[0]}/'

    # Token-overlap against products: pick the product whose slug
    # shares the most tokens with the 404 path.
    if tokens and product_slugs:
        best_slug, best_score = '', 0
        for slug in product_slugs:
            slug_tokens = {t for t in slug.split('-') if len(t) >= 3}
            overlap = sum(1 for t in tokens if t in slug_tokens)
            if overlap > best_score:
                best_score, best_slug = overlap, slug
        if best_score >= 2:
            return f'/products/{best_slug}/'

    # Category fallback.
    try:
        cat_slugs = list(Category.objects.values_list('slug', flat=True))
    except Exception:  # noqa: BLE001
        cat_slugs = []
    if cat_slugs and target_slug:
        close = difflib.get_close_matches(target_slug, cat_slugs, n=1, cutoff=0.6)
        if close:
            return f'/products/?category={close[0]}'
        for token in tokens:
            if token in cat_slugs:
                return f'/products/?category={token}'

    # Legacy contains-substring fallback (kept for backward parity).
    try:
        for token in tokens:
            if len(token) < 3:
                continue
            p = Product.objects.filter(slug__icontains=token, status='active').first()
            if p:
                return f'/products/{p.slug}/'
    except Exception:  # noqa: BLE001, S110
        pass
    return ''


def _path_from_history(path: str) -> str:
    """The current path of whatever object used to live at ``path``."""
    from plugins.installed.seo.models import SlugHistory

    try:
        row = (
            SlugHistory.objects.filter(old_path=normalise_path(path))
            .order_by('-created_at')
            .first()
        )
    except Exception:  # noqa: BLE001
        return ''
    return row.new_path if row else ''


def refresh_404_suggestions(*, limit: int = 50) -> int:
    """Fill in suggested_target on the top unresolved 404s."""
    from plugins.installed.seo.models import NotFoundLog

    n = 0
    rows = NotFoundLog.objects.filter(is_resolved=False).order_by('-hit_count')[:limit]
    for row in rows:
        if row.suggested_target:
            continue
        target = suggest_redirect(row.path)
        if target:
            row.suggested_target = target
            row.save(update_fields=['suggested_target'])
            n += 1
    return n
