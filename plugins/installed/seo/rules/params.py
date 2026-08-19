"""Per-parameter index policy: the canonical, and whether to index at all.

One function does the work — `decide_params(query)` — and everything that has
an opinion about a URL's query string reads it: the head builder (canonical +
robots), the dashboard's URL preview, and robots.txt (for the parameters whose
policy is to never be fetched at all).

Three properties are worth stating because each one replaces a defect:

* **A no-indexed page keeps its own parameters in its canonical.** The previous
  arrangement stripped every parameter *and* set `noindex` when a listed one was
  present, so a facet page announced "do not index me" while its canonical named
  the category — two contradictory statements about two different URLs, and the
  documented risk is that the `noindex` travels to the canonical target and
  takes the category with it. A page is either consolidated or no-indexed, never
  both.

* **The surviving parameters are sorted and de-duplicated.** `?a=1&b=2` and
  `?b=2&a=1` are the same page; emitting them as two canonicals splits whatever
  signal the page had earned in half.

* **Rules are compiled once and cached.** This runs on every storefront page
  render, so a per-request query over a table with a handful of rows would be a
  tax on the whole site. The cache is dropped on write (`signals.py`), because a
  merchant who changes a rule and sees nothing happen concludes it is broken.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode

from plugins.installed.seo.rules.pagination import page_value

logger = logging.getLogger('morpheus.seo')

_RULES_CACHE_KEY = 'seo:index_rules:v1'
_RULES_CACHE_TTL = 600

# `page` is deliberately not addressable by a rule. Pagination has its own
# policy (see `rules/pagination.py`) and the one thing a merchant must not be
# able to do by accident is canonicalise page 2 onto page 1, which de-indexes
# every product that is not on the first screen.
RESERVED_PARAMS = frozenset({'page'})

# What a store usually wants, offered as a one-click starter set on the Index
# rules page rather than seeded by a migration. These are opinions about a
# merchant's URLs, and an opinion that installs itself is the "settings field
# with no consumer" problem inverted: a consumer nobody asked for.
RECOMMENDED_RULES: tuple[tuple[str, str, str], ...] = (
    ('utm_*', 'consolidate', 'Campaign tracking — the same page, arrived at differently.'),
    ('gclid', 'consolidate', 'Google Ads click id.'),
    ('fbclid', 'consolidate', 'Meta click id.'),
    ('msclkid', 'consolidate', 'Microsoft Ads click id.'),
    ('sort', 'consolidate', 'Same products, different order.'),
    ('view', 'consolidate', 'Grid or list — a display preference, not a page.'),
    ('q', 'noindex', 'Internal search results: an unbounded set of thin pages.'),
    ('price_min', 'noindex', 'Numeric filter — every value is another near-duplicate.'),
    ('price_max', 'noindex', 'Numeric filter — every value is another near-duplicate.'),
)


@dataclass(frozen=True, slots=True)
class ParamDecision:
    """What the query string means for this URL."""

    query: str
    """The canonical query string — normalised, sorted, policy-filtered."""

    noindex_params: tuple[str, ...] = ()
    """Parameters whose policy holds this page back, for the robots reason."""

    @property
    def noindex(self) -> bool:
        return bool(self.noindex_params)


def decide_params(query: str, *, paginated: bool = False) -> ParamDecision:
    """Apply the index rules to a raw query string.

    `paginated` says whether the page being rendered actually has a paginator.
    It defaults to False because a `?page=` on a page that does not paginate is
    not pagination — it is noise the URL happened to carry, and echoing it into
    a self-canonical is how `/shop/?page=999` came to be its own indexable page
    on a listing that renders every product on one screen.
    """
    if not query:
        return ParamDecision(query='')

    rules = _rules()
    default_consolidates = _consolidate_unlisted()
    kept: list[tuple[str, str]] = []
    noindexed: list[str] = []

    for key, value in parse_qsl(query, keep_blank_values=True):
        lowered = key.lower()
        if lowered in RESERVED_PARAMS:
            # `?page=1` is the clean URL wearing a hat; page 2 of a real
            # paginator is its own self-canonical page of results. Compared
            # numerically, because a paginator reads `int(value)` — so `?page=01`
            # renders page 1, and a string comparison would let it keep a
            # canonical of its own and become exactly the duplicate this
            # release exists to remove.
            if paginated and page_value(value) > 1:
                kept.append((key, value))
            continue

        rule = _rule_for(lowered, rules)
        if rule is None:
            if not default_consolidates:
                kept.append((key, value))
            continue

        policy, allowed = rule
        if policy in ('consolidate', 'block'):
            # `block` never reaches a crawler at all (robots.txt stops the
            # fetch), so its page-level treatment only matters to a human or a
            # bot that ignored robots — consolidating is the safe reading.
            continue
        if policy == 'allowlist' and value.strip() in allowed:
            kept.append((key, value))
            continue
        # `noindex`, and any allowlist value that is not on the list.
        kept.append((key, value))
        if lowered not in noindexed:
            noindexed.append(lowered)

    return ParamDecision(query=_normalise(kept), noindex_params=tuple(noindexed))


def blocked_param_patterns() -> tuple[str, ...]:
    """robots.txt `Disallow` patterns for every parameter policied `block`.

    `/*?*sort=` is the shape Google documents for parameter blocking: any path,
    a query string somewhere in it, then the parameter. It deliberately does not
    anchor on `?` — `/books/?a=1&sort=x` has to match too.

    A wildcard rule stops at the prefix and drops the `=`: `utm_*` has to match
    `?utm_source=`, and `/*?*utm_=` matches nothing at all.
    """
    rules = _rules()
    patterns = [
        f'/*?*{param}=' for param, (policy, _) in rules['exact'].items() if policy == 'block'
    ]
    # A wildcard whose prefix also captures `page` would emit `Disallow: /*?*page`
    # and stop crawlers reaching page 2 of every listing on the store. The
    # reservation has to hold for every spelling that reaches a reserved
    # parameter, not only for the literal name.
    patterns += [
        f'/*?*{prefix}'
        for prefix, policy, _ in rules['wildcards']
        if policy == 'block' and not captures_reserved(f'{prefix}*')
    ]
    return tuple(sorted(set(patterns)))


def captures_reserved(param: str) -> bool:
    """Would a rule named `param` apply to a parameter the platform reserves?"""
    cleaned = (param or '').strip().lower()
    if cleaned in RESERVED_PARAMS:
        return True
    return cleaned.endswith('*') and any(r.startswith(cleaned[:-1]) for r in RESERVED_PARAMS)


def invalidate_index_rules_cache() -> None:
    """Drop the compiled ruleset. Hangs off post_save/post_delete."""
    from django.core.cache import cache

    try:
        cache.delete(_RULES_CACHE_KEY)
    except Exception:  # noqa: BLE001 — a broken cache must not break a save
        logger.debug('seo: index rule cache invalidation failed', exc_info=True)


# -- compilation ---------------------------------------------------------
def _rules() -> dict:
    from django.core.cache import cache

    try:
        cached = cache.get(_RULES_CACHE_KEY)
        if cached is not None:
            return cached
    except Exception:  # noqa: BLE001
        return _compile()
    rules = _compile()
    try:
        cache.set(_RULES_CACHE_KEY, rules, _RULES_CACHE_TTL)
    except Exception:  # noqa: BLE001
        logger.debug('seo: could not cache index rules', exc_info=True)
    return rules


def _compile() -> dict:
    """`{'exact': {param: (policy, frozenset)}, 'wildcards': [(prefix, policy, frozenset)]}`.

    Longest wildcard prefix first, so `utm_source_*` beats `utm_*` if a merchant
    ever writes both — the same first-match-wins precedence the redirect
    resolver uses, for the same reason.

    The legacy `SiteSeoSettings.noindex_query_params` list is read FIRST and any
    real rule overrides it. That list was the whole of this feature before v0.50
    and it is still what an upgrading store has configured; dropping its reader
    the moment a better table exists is how a merchant's setting silently stops
    working. It goes away with the column (see docs/MIGRATING.md).
    """
    exact: dict[str, tuple[str, frozenset[str]]] = dict(_legacy_noindex_params())
    wildcards: list[tuple[str, str, frozenset[str]]] = []
    try:
        from plugins.installed.seo.models import IndexRule

        rows = list(
            IndexRule.objects.filter(is_active=True).values('param', 'policy', 'allowed_values')
        )
    except Exception:  # noqa: BLE001 — an unmigrated table mid-deploy
        return {'exact': {}, 'wildcards': []}

    for row in rows:
        param = (row['param'] or '').strip().lower()
        if not param or param in RESERVED_PARAMS:
            continue
        allowed = frozenset(str(v).strip() for v in (row['allowed_values'] or []))
        if param.endswith('*'):
            wildcards.append((param[:-1], row['policy'], allowed))
        else:
            exact[param] = (row['policy'], allowed)

    wildcards.sort(key=lambda w: len(w[0]), reverse=True)
    return {'exact': exact, 'wildcards': wildcards}


def _legacy_noindex_params() -> list[tuple[str, tuple[str, frozenset[str]]]]:
    """`SiteSeoSettings.noindex_query_params` as implicit no-index rules."""
    try:
        from plugins.installed.seo.services import site_settings

        names = site_settings().noindex_query_params or []
    except Exception:  # noqa: BLE001 — unmigrated, or the app is mid-boot
        return []
    return [
        (name, ('noindex', frozenset()))
        for name in ((str(p) or '').strip().lower() for p in names)
        if name and name not in RESERVED_PARAMS
    ]


def _rule_for(param: str, rules: dict) -> tuple[str, frozenset[str]] | None:
    hit = rules['exact'].get(param)
    if hit is not None:
        return hit
    for prefix, policy, allowed in rules['wildcards']:
        if param.startswith(prefix):
            return policy, allowed
    return None


def _normalise(pairs: list[tuple[str, str]]) -> str:
    """Sorted, de-duplicated, re-encoded."""
    return urlencode(sorted(set(pairs)))


def _consolidate_unlisted() -> bool:
    """What happens to a parameter no rule mentions.

    Defaults to consolidating, which is right for a store: parameters appear on
    storefront URLs faster than a merchant writes rules for them (a new campaign
    tool, an app's `?ref=`), and the failure mode of consolidating one that
    deserved its own page is a missed opportunity, while the failure mode of
    keeping one that did not is duplicate pages competing with each other.
    """
    try:
        from plugins.installed.seo.services import _seo_plugin_cfg

        cfg = _seo_plugin_cfg()
        return bool(cfg.get('canonical_strip_query_params', True)) if cfg else True
    except Exception:  # noqa: BLE001
        return True
