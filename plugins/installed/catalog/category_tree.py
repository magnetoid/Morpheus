"""A category lists its own products and those of every active category below it.

One place for the rule, read by the storefront's category page and shop filter,
the GraphQL products query, Linda's product tools and the dashboard's category
counts, so they agree on what "in Tech" means. A switched-off category hides
its own branch: its products are not listed under its parent, and its
subcategories drop out of the tree.
"""

from __future__ import annotations

from collections import defaultdict

from django.db.models import Q


def _active_children() -> dict:
    from plugins.installed.catalog.models import Category

    kids = defaultdict(list)
    for pk, parent in Category.objects.filter(is_active=True).values_list('pk', 'parent_id'):
        kids[parent].append(pk)
    return kids


def subtree_ids(categories) -> set:
    """The pks of ``categories`` and of every active category below them."""
    kids = _active_children()
    ids: set = set()
    stack = [c.pk for c in categories]
    while stack:
        pk = stack.pop()
        if pk not in ids:
            ids.add(pk)
            stack.extend(kids.get(pk, ()))
    return ids


def in_categories(categories) -> Q:
    """Products whose category, or a category they are cross-listed in, sits in
    the subtree of ``categories``. Filter with ``.distinct()``: the cross-listing
    join can repeat a row."""
    ids = subtree_ids(categories)
    return Q(category__in=ids) | Q(additional_categories__in=ids)


def display_tree() -> list:
    """Active categories in display order, each top level followed by its
    subcategories; every row carries ``depth`` (0 for a top level)."""
    from plugins.installed.catalog.models import Category

    kids = defaultdict(list)
    for c in Category.objects.filter(is_active=True):
        kids[c.parent_id].append(c)
    out: list = []

    def walk(parent, depth):
        for c in sorted(kids.get(parent, ()), key=lambda c: (c.sort_order, c.name.lower())):
            c.depth = depth
            out.append(c)
            walk(c.pk, depth + 1)

    walk(None, 0)
    return out
