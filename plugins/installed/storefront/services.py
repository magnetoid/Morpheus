"""Storefront services — helpers shared across the view modules."""

from __future__ import annotations


def page_intro(request, page: str) -> dict:
    """Merchant-edited intro copy + meta for a built-in listing page.

    ``/products/``, ``/vendors/`` and ``/journal/`` are code-owned listings
    that own no model of their own — unlike a Category, a Collection or a
    BookTaxonomyRoot, each of which carries its own editable intro. Their
    prose was therefore hardcoded in the theme (and their meta description
    hardcoded in the view), with no way for a merchant to change either.

    Fire the ``STOREFRONT_PAGE_INTRO`` filter and let whichever plugin owns
    editable copy supply it (cms does, from a Block keyed ``<page>_intro``).
    Going through the bus rather than importing cms keeps this disable-safe:
    the hook registry skips inactive owners, so a disabled cms degrades to
    the theme's static fallback instead of 500ing the storefront.

    Returns ``{'body': str, 'meta_description': str}`` — both '' when nothing
    is configured, which is the caller's cue to keep its fallback copy.
    """
    from morpheus.core import MorpheusEvents, hook_registry  # noqa: PLC0415

    empty = {'body': '', 'meta_description': ''}
    result = hook_registry.filter(
        MorpheusEvents.STOREFRONT_PAGE_INTRO,
        value=dict(empty),
        page=page,
        request=request,
    )
    return result if isinstance(result, dict) else empty
