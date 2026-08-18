"""Extract a comparable *profile* of a rendered page's ``<head>``.

This is the measuring instrument for the SEO 3.0 rewrite: the profile of every
storefront page type is snapshotted against the CURRENT implementation
(``fixtures/head_profiles.json``) and re-asserted after the head pipeline moves
into the kernel. It exists so "the theme no longer calls ``{% seo_meta %}``"
cannot silently mean "the canonical is gone".

Parsing is stdlib ``html.parser`` on purpose — lxml/bs4 are not dependencies and
a native dep that loads at import is deploy-critical (CLAUDE.md).
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser

# Head keys that carry SEO meaning. Anything outside this list (viewport,
# theme-color, csrf, …) is deliberately ignored: the parity test is about SEO
# output, not about byte-identical markup.
_META_NAMES = (
    'description',
    'robots',
    'googlebot',
    'bingbot',
    'keywords',
    'author',
    'google-site-verification',
    'msvalidate.01',
    'p:domain_verify',
    'facebook-domain-verification',
    'twitter:card',
    'twitter:title',
    'twitter:description',
    'twitter:image',
    'twitter:site',
    'twitter:creator',
)
_META_PROPERTIES = (
    'og:title',
    'og:description',
    'og:type',
    'og:url',
    'og:image',
    'og:image:secure_url',
    'og:image:alt',
    'og:image:width',
    'og:image:height',
    'og:site_name',
    'og:locale',
    'product:price:amount',
    'product:price:currency',
    'product:availability',
)
_LINK_RELS = ('canonical', 'alternate', 'next', 'prev', 'search', 'amphtml')

_WS = re.compile(r'\s+')


def _norm(value: str) -> str:
    return _WS.sub(' ', (value or '').strip())


class _HeadParser(HTMLParser):
    """Collect title / meta / link / JSON-LD from the document head."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ''
        self.metas: dict[str, str] = {}
        self.links: list[dict[str, str]] = []
        self.jsonld_raw: list[str] = []
        self._in_head = True
        self._capture = ''  # 'title' | 'jsonld' | ''
        self._buf: list[str] = []

    # -- tags ------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        attr = {k.lower(): (v or '') for k, v in attrs}
        if tag == 'title' and self._in_head and not self.title:
            self._capture = 'title'
            self._buf = []
        elif tag == 'meta' and self._in_head:
            key = (attr.get('name') or attr.get('property') or '').strip()
            if key in _META_NAMES or key in _META_PROPERTIES:
                # First writer wins, and a duplicate is itself a finding: record
                # the repeat under a suffixed key so the diff shows it.
                if key in self.metas:
                    self.metas[f'{key}#dup'] = _norm(attr.get('content', ''))
                else:
                    self.metas[key] = _norm(attr.get('content', ''))
        elif tag == 'link' and self._in_head:
            rel = (attr.get('rel') or '').strip().lower()
            if rel in _LINK_RELS:
                entry = {'rel': rel, 'href': _norm(attr.get('href', ''))}
                for extra in ('hreflang', 'type', 'title'):
                    if attr.get(extra):
                        entry[extra] = _norm(attr[extra])
                self.links.append(entry)
        elif tag == 'script' and 'ld+json' in attr.get('type', ''):
            self._capture = 'jsonld'
            self._buf = []

    def handle_endtag(self, tag):
        if tag == 'title' and self._capture == 'title':
            self.title = _norm(''.join(self._buf))
            self._capture = ''
        elif tag == 'script' and self._capture == 'jsonld':
            self.jsonld_raw.append(''.join(self._buf))
            self._capture = ''
        elif tag == 'head':
            self._in_head = False

    def handle_data(self, data):
        if self._capture:
            self._buf.append(data)


def _jsonld_summary(raw_blocks: list[str]) -> list[dict]:
    """Reduce every JSON-LD block to {type, id, props} entries.

    Property *values* are kept only for the fields SEO correctness depends on;
    everything else is reduced to the property name, so the rewrite may add
    properties (it must, per Google's 2026 rules) but may never drop one.
    """
    valued = {
        'name',
        'url',
        'headline',
        'price',
        'priceCurrency',
        'availability',
        'itemCondition',
        'sku',
        'gtin13',
        'isbn',
        'position',
        'inLanguage',
        'numberOfItems',
        'ratingValue',
        'reviewCount',
    }
    out: list[dict] = []

    def visit(node, depth=0):
        if isinstance(node, list):
            for item in node:
                visit(item, depth)
            return
        if not isinstance(node, dict):
            return
        node_type = node.get('@type')
        if node_type:
            entry = {
                'type': node_type if isinstance(node_type, str) else sorted(node_type),
                'props': sorted(k for k in node if not k.startswith('@')),
            }
            if node.get('@id'):
                entry['id'] = node['@id']
            values = {k: node[k] for k in sorted(valued & set(node)) if _scalar(node[k])}
            if values:
                entry['values'] = values
            out.append(entry)
        # Recurse into containers so nested Offer/Brand/ItemList nodes count.
        # `@graph` is the one `@`-prefixed key that holds nodes rather than
        # metadata — skipping it (as the other `@…` keys are skipped) would make
        # a whole graph document look like zero structured data.
        for key, value in node.items():
            if key.startswith('@') and key != '@graph':
                continue
            if isinstance(value, dict | list):
                visit(value, depth + 1)

    for raw in raw_blocks:
        try:
            visit(json.loads(raw))
        except (ValueError, TypeError):
            out.append({'type': '__unparseable__', 'props': [], 'raw': _norm(raw)[:120]})
    out.sort(key=lambda e: (str(e['type']), e.get('id', '')))
    return out


def _scalar(value) -> bool:
    return isinstance(value, str | int | float) and not isinstance(value, bool)


def head_profile(html: str, *, path: str = '', status: int = 200) -> dict:
    """Return the SEO-relevant shape of a rendered page."""
    parser = _HeadParser()
    parser.feed(html)
    parser.close()
    profile = {
        'path': path,
        'status': status,
        'title': parser.title,
        'meta': dict(sorted(parser.metas.items())),
        'links': sorted(
            parser.links, key=lambda link: (link['rel'], link.get('hreflang', ''), link['href'])
        ),
        'jsonld': _jsonld_summary(parser.jsonld_raw),
        'title_count': html.count('<title'),
        'canonical_count': sum(1 for link in parser.links if link['rel'] == 'canonical'),
        'robots_count': 1 if 'robots' in parser.metas else 0,
    }
    if 'robots#dup' in parser.metas:
        profile['robots_count'] = 2
    return profile


def robots_directives(value: str) -> set[str]:
    """`index, follow, max-snippet:-1` → an order-insensitive directive set."""
    return {part.strip().lower() for part in (value or '').split(',') if part.strip()}


def diff_profiles(before: dict, after: dict) -> list[str]:
    """Human-readable regressions of `after` against the recorded `before`.

    Rules: title/description/canonical/robots/OG/Twitter must match exactly
    (robots order-insensitively). JSON-LD may GAIN types and properties but may
    not lose a type, an `@id`, a property, or change a recorded value.
    """
    problems: list[str] = []
    if before.get('status') != after.get('status'):
        problems.append(f'status {before.get("status")} → {after.get("status")}')
    if _norm(before.get('title', '')) != _norm(after.get('title', '')):
        problems.append(f'title {before.get("title")!r} → {after.get("title")!r}')
    if after.get('title_count') != before.get('title_count'):
        # Any change in how many <title> elements a page emits is worth a human
        # look: 1→2 is a duplicate-emission bug, 1→0 loses the title, and 0→1 is
        # the /search/ fix landing (re-record). The absolute "exactly one"
        # invariant is asserted separately, with its own shrinking allowlist.
        problems.append(f'<title> count {before.get("title_count")} → {after.get("title_count")}')
    if after.get('canonical_count', 1) > 1:
        problems.append(f'{after.get("canonical_count")} canonical links')
    if after.get('robots_count', 1) > 1:
        problems.append('duplicate robots meta')

    before_meta, after_meta = before.get('meta', {}), after.get('meta', {})
    for key, value in before_meta.items():
        if key.endswith('#dup'):
            continue  # a duplicate in the OLD output is a bug, not a contract
        got = after_meta.get(key)
        if got is None:
            problems.append(f'meta {key} lost (was {value!r})')
        elif key == 'robots':
            if robots_directives(value) != robots_directives(got):
                problems.append(f'meta robots {value!r} → {got!r}')
        elif _norm(value) != _norm(got):
            problems.append(f'meta {key} {value!r} → {got!r}')

    def link_key(link):
        return (link['rel'], link.get('hreflang', ''), link['href'])

    after_links = {link_key(link) for link in after.get('links', [])}
    for link in before.get('links', []):
        if link_key(link) not in after_links:
            problems.append(f'link lost: {link}')

    # JSON-LD is compared per @type, not per node: sibling nodes of the same type
    # (ListItem, Offer, …) have no stable identity across renders, so a
    # positional comparison would report pure noise. Per type we require the
    # union of properties and the set of recorded values to survive — which
    # still catches "Product lost its offers", "breadcrumb lost a crumb name",
    # or "price changed", while tolerating reordering and de-duplication.
    before_by_type = _group_by_type(before.get('jsonld', []))
    after_by_type = _group_by_type(after.get('jsonld', []))
    for node_type, (props, values) in before_by_type.items():
        target = after_by_type.get(node_type)
        if target is None:
            problems.append(f'jsonld {node_type} lost (types now: {sorted(after_by_type)})')
            continue
        missing_props = sorted(props - target[0])
        if missing_props:
            problems.append(f'jsonld {node_type} lost props {missing_props}')
        for prop, value in sorted(values - target[1]):
            problems.append(f'jsonld {node_type}.{prop} lost value {value!r}')
    return problems


def _group_by_type(nodes: list[dict]) -> dict[str, tuple[set[str], set[tuple[str, object]]]]:
    grouped: dict[str, tuple[set[str], set[tuple[str, object]]]] = {}
    for node in nodes:
        node_type = str(node['type'])
        props, values = grouped.setdefault(node_type, (set(), set()))
        props.update(node.get('props', []))
        values.update((k, v) for k, v in (node.get('values') or {}).items())
    return grouped
