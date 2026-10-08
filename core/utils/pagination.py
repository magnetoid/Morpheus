"""Pagination a storefront can stand behind.

Two rules every listing on every store follows, so they live in one place:

* **A page that does not exist is a 404.** Django's `Paginator.get_page` clamps
  `?page=999` back to page 1 — friendly for a person who mistyped, expensive
  for a store: every integer became a 200 serving page 1 under its own URL.
* **Page 1 is the clean URL.** `?page=1` 301s to it (seo's middleware), so a
  "previous" link that names it costs every visitor and crawler a redirect hop.
  `page_href` builds the link the way the canonical names the page.

Used by the storefront and by any app that renders a listing (book facets,
journal, vendor pages); core holds it because a helper several plugins share
cannot live in one of them without a plugin→plugin import.
"""

from __future__ import annotations

from urllib.parse import urlencode


def paginate_or_404(object_list, per_page: int, request):
    """The requested page of `object_list`, or Http404 when it is not a page.

    Page 1 of an empty list is still a page (Django's `allow_empty_first_page`),
    so an empty listing renders — and the SEO layer, reading the paginator's
    count, keeps it out of the index.
    """
    from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
    from django.http import Http404

    try:
        return Paginator(object_list, per_page).page(request.GET.get('page') or 1)
    except (EmptyPage, PageNotAnInteger):
        raise Http404('No such page of results.') from None


def page_href(request, number) -> str:
    """Path + query for page `number` of the listing `request` is on.

    Keeps every other parameter (filters, sort, search), drops `page` for page 1.
    """
    try:
        number = int(number)
    except (TypeError, ValueError):
        number = 1
    pairs = [
        (key, value) for key, values in request.GET.lists() if key != 'page' for value in values
    ]
    if number > 1:
        pairs.append(('page', str(number)))
    return f'{request.path}?{urlencode(pairs)}' if pairs else request.path
