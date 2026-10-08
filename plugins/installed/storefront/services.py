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


def store_name() -> str:
    """The merchant's own store name — never a hardcoded brand.

    The shell shipped `dot books` inside SEO descriptions on /about/,
    /contact/, /shipping/, /products/, /search/ and author pages, so every
    other store on the platform published a different business's name to
    Google. supernatural-shop.com told searchers "dot books is an independent
    bookshop", and montenegro-experience.me advertised dot books' shipping
    terms. Those are two live brands describing themselves as a third.
    """
    from core.models import StoreSettings

    # Lowercase on purpose: the name is always used mid-sentence ("Browse
    # everything this shop sells"), and a capitalised fallback reads as a
    # proper noun — "About This shop." A store row always carries a name, so
    # this only appears before the merchant has set one up.
    return (StoreSettings.get('store_name', '') or '').strip() or 'this shop'


def store_blurb() -> str:
    """The merchant's own store description, or '' when they haven't written one.

    Empty on purpose when unset: the seo app's fallback chain produces a better
    description from the page than the shell can invent, and an invented one is
    how a bookshop's copy ended up on a travel marketplace.
    """
    from core.models import StoreSettings

    for key in ('meta_description', 'store_description'):
        value = (StoreSettings.get(key, '') or '').strip()
        if value:
            return value
    return ''


def catalogue_label() -> str:
    """What this store calls "everything it sells", for titles + breadcrumbs.

    `All books` was hardcoded in six places in the shell, so an oils shop's
    product listing was titled "All books" with a breadcrumb to match. The book
    vertical owns that word; every other store gets the neutral one.
    """
    from plugins.registry import app_registry

    return 'All books' if app_registry.is_active('book_product') else 'All products'


def staff_picks_collection():
    """The collection behind /staff-picks/ — `staff-picks`, else the legacy slug."""
    from plugins.installed.catalog.models import Collection

    return (
        Collection.objects.filter(slug='staff-picks', is_active=True).first()
        or Collection.objects.filter(slug='editors-pick-april', is_active=True).first()
    )


def stocked_category_ids() -> set:
    """Pks of active categories that list at least one active product.

    The same membership `category_detail` renders — the primary category OR the
    cross-listing M2M — so the category index, the sitemap and the page agree on
    which categories have anything on them.
    """
    from django.db.models import Q

    from plugins.installed.catalog.models import Category

    return set(
        Category.objects.filter(is_active=True)
        .filter(Q(products__status='active') | Q(also_listed_products__status='active'))
        .values_list('pk', flat=True)
        .distinct()
    )


def journal_has_entries() -> bool:
    """Whether /journal/ would list at least one live post."""
    from plugins.registry import app_registry

    if not app_registry.is_active('cms'):
        return False
    try:
        from plugins.installed.cms.services import list_journal_entries  # noqa: PLC0415

        return bool(list_journal_entries(limit=1))
    except Exception:  # noqa: BLE001 — a broken cms must not break the sitemap
        return False


def vendor_nouns() -> tuple[str, str]:
    """`(singular, plural)` — what this store calls its vendors, in the visitor's language.

    The active theme says it (`MorpheusTheme.vendor_noun`): the shell used to
    hardcode "Publishers", so a travel host's page was "<Host> — Publishers".
    """
    from django.utils.translation import gettext

    from themes.registry import theme_registry

    theme = theme_registry.active
    single = getattr(theme, 'vendor_noun', '') or 'Seller'
    plural = getattr(theme, 'vendor_noun_plural', '') or 'Sellers'
    return gettext(single), gettext(plural)
