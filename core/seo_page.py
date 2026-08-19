"""The vocabulary the `SEO_RESOLVE_PAGE` seam speaks.

Core owns the *shape* of a resolved page; the seo app owns the rules that turn
one into markup (ADR 0017, the same split as `core/head.py` and its
`HeadDocument`). It lives here rather than inside the seo app for a concrete
reason: an app that owns a family of storefront URLs — book_product's author and
taxonomy landings, marketplace's vendor pages — answers the filter by *building
one of these*, and it must be able to do that without importing the seo app,
which it does not depend on and which may be disabled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Page kinds. The set is deliberately small: it exists to answer "how should
# this page behave in search", not to mirror every URL the storefront has.
#
#   home / static      — indexable, brand-owned copy, no object
#   product            — the money page; full Product markup
#   listing            — PLP, category, collection, vendor, author, taxonomy,
#                        journal index: a page *of* other pages
#   article            — journal/blog detail
#   page               — a CMS page
#   search             — internal search results: noindex, follow (crawl the
#                        links, don't index the query permutations)
#   private            — cart/checkout/account/auth: noindex, nofollow
KIND_HOME = 'home'
KIND_STATIC = 'static'
KIND_PRODUCT = 'product'
KIND_LISTING = 'listing'
KIND_ARTICLE = 'article'
KIND_PAGE = 'page'
KIND_SEARCH = 'search'
KIND_PRIVATE = 'private'

_INDEXABLE_KINDS = frozenset(
    {KIND_HOME, KIND_STATIC, KIND_PRODUCT, KIND_LISTING, KIND_ARTICLE, KIND_PAGE}
)


@dataclass(slots=True)
class SeoPage:
    """One page, described in the terms search engines care about."""

    kind: str = KIND_STATIC
    obj: Any = None  # the MODEL instance the page is about (SeoMeta hangs off it)
    # What the template actually rendered. The PDP renders a GraphQL dict with
    # price, stock and images already resolved, while the view's model row has
    # `price` deferred — so structured data and Open Graph read this, and
    # merchant overrides (SeoMeta, native columns) read `obj`. Keeping them
    # separate is what stops "markup must match the visible content" from being
    # a matter of luck.
    rendered: Any = None
    path: str = ''
    title: str = ''  # CLEAN page name — the brand is applied at render (ADR 0007)
    description: str = ''
    image: str = ''
    og_type: str = 'website'
    subtype: str = ''  # 'category' | 'collection' | 'vendor' | 'author' | …
    noindex: bool = False
    nofollow: bool = False
    reason: str = ''  # why it is noindexed — surfaced in the inspector
    brand_title: bool = True  # False for pages whose title already IS the brand
    breadcrumbs: list = field(default_factory=list)
    page_obj: Any = None  # Django Paginator page, when the page is paginated
    query: str = ''  # the search term, for search pages
    language: str = ''
    context: dict = field(default_factory=dict)  # the flattened template context

    @property
    def indexable(self) -> bool:
        return self.kind in _INDEXABLE_KINDS and not self.noindex

    def deny_index(self, reason: str, *, nofollow: bool = False) -> None:
        """Mark the page noindex, recording WHY.

        The reason is not decoration: "this page is noindex" with no explanation
        is the single most expensive thing to debug in an SEO system, because
        the merchant sees a page missing from Google and has nowhere to look.
        """
        self.noindex = True
        self.nofollow = self.nofollow or nofollow
        if reason and reason not in self.reason:
            self.reason = f'{self.reason}; {reason}'.strip('; ')

    def robots(self) -> str:
        index = 'noindex' if self.noindex else 'index'
        follow = 'nofollow' if self.nofollow else 'follow'
        return f'{index}, {follow}'
