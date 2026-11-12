"""A page's breadcrumb trail: one list, rendered twice (v0.161.0).

A view puts `breadcrumb_items` (``[{'name', 'url'}, …]``, absolute urls, the page
itself last) in its context. The head's BreadcrumbList is built from it, and so is
the visible trail (`{% breadcrumb_trail %}`, storefront/_breadcrumb_trail.html,
which a theme restyles but never rewrites). Until v0.161.0 the product page's
markup named a filter address (`/products/?category=<slug>`, which canonicalises
to `/products/`) while the visible trail linked `/category/<slug>/` or a genre and
called the catalogue something else.

This module builds the part between the catalogue and the product: the product's
category with its active ancestors, which an app that owns a better parent page
may replace through PRODUCT_BREADCRUMB_CATEGORY (book_product: a book's genre).
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.storefront')


def category_crumbs(category, request) -> list[dict]:
    """`category` and its active ancestors, root first, each at /category/<slug>/.

    A switched-off category has no page, so it has no crumb, and the categories
    above a switched-off one are left out: its branch is hidden from them
    (catalog/category_tree.py), so their pages do not list this product.
    """
    if category is None or not getattr(category, 'is_active', False):
        return []
    chain = [category]
    try:
        for parent in category.get_ancestors(ascending=True):
            if not parent.is_active:
                break
            chain.append(parent)
    except Exception as e:  # noqa: BLE001 — a broken tree keeps the category's own crumb
        logger.warning('storefront: category ancestors failed for %s: %s', category.pk, e)
    return [
        {'name': c.name, 'url': request.build_absolute_uri(f'/category/{c.slug}/')}
        for c in reversed(chain)
    ]


def product_category_crumbs(request, *, product=None, category=None) -> list[dict]:
    """The crumbs between the catalogue and the product: the category default, or an app's.

    `product` is the product page's catalog row (else its GraphQL dict), None on the
    product list; `category` is the catalog Category the default is built from.
    """
    from morpheus.core import MorpheusEvents, hook_registry  # noqa: PLC0415

    default = category_crumbs(category, request)
    try:
        answer = hook_registry.filter(
            MorpheusEvents.PRODUCT_BREADCRUMB_CATEGORY,
            list(default),
            product=product,
            category=category,
            request=request,
        )
    except Exception as e:  # noqa: BLE001 — an answer never costs the page its trail
        logger.warning('storefront: PRODUCT_BREADCRUMB_CATEGORY failed: %s', e, exc_info=True)
        return default
    if not isinstance(answer, list):
        return default
    return [
        {'name': str(item['name']), 'url': str(item['url'])}
        for item in answer
        if isinstance(item, dict) and item.get('name') and item.get('url')
    ]
